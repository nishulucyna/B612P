// Whisper text decoder on the Hexagon DSP/HTP through SNPE.
//
// The decoder DLC (scripts/whisper_build/export_decoder.py) has fixed shapes and no KV cache:
//   emb    float (L, D)       token + positional embedding of the padded ids, built here on the CPU from whisper_<size>_embed.bin
//                             (ids cannot be graph inputs: an fp16 graph cannot hold integers above 2048 exactly)
//   xa     float (1500, D)    encoder output
//   idx    float (1)          position whose next-token logits are wanted
//   logits float (1, V)
// Greedy decoding runs here, so the 4.6 MB encoder output is handed to SNPE once per utterance instead of crossing JNI each step.

#include <jni.h>
#include <string>
#include <vector>
#include <memory>
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <cstdint>
#include "android/log.h"

#include "zdl/SNPE/SNPE.hpp"
#include "zdl/SNPE/SNPEFactory.hpp"
#include "zdl/DlSystem/DlEnums.hpp"
#include "zdl/DlSystem/ITensor.hpp"
#include "zdl/DlSystem/TensorMap.hpp"
#include "zdl/DlSystem/TensorShape.hpp"
#include "zdl/DlSystem/StringList.hpp"
#include "zdl/DlContainer/IDlContainer.hpp"
#include "DlSystem/ITensorFactory.hpp"

#include "hpp/SetBuilderOptions.hpp"

#define DLOGI(...) __android_log_print(ANDROID_LOG_INFO, "WhisperDecoder", __VA_ARGS__)
#define DLOGE(...) __android_log_print(ANDROID_LOG_ERROR, "WhisperDecoder", __VA_ARGS__)

namespace {
std::unique_ptr<zdl::SNPE::SNPE> g_snpe;
std::unique_ptr<zdl::DlSystem::ITensor> g_emb, g_xa, g_idx;
size_t g_len = 0;          // L
size_t g_dim = 0;          // D
std::vector<uint16_t> g_embedTable;   // L x D positional rows, then V x D token rows, fp16

float halfToFloat(uint16_t h) {
    uint32_t sign = (uint32_t) (h & 0x8000) << 16, exp = (h >> 10) & 0x1f, mant = h & 0x3ff, bits;
    if (exp == 0) {
        if (mant == 0) bits = sign;
        else { exp = 127 - 14; while (!(mant & 0x400)) { mant <<= 1; exp--; } mant &= 0x3ff; bits = sign | (exp << 23) | (mant << 13); }
    } else if (exp == 31) bits = sign | 0x7f800000 | (mant << 13);
    else bits = sign | ((exp + 112) << 23) | (mant << 13);
    float f; memcpy(&f, &bits, 4); return f;
}
std::string g_lastError;
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_b612p_npubridge_WhisperDecoderNative_load(JNIEnv *env, jobject, jstring dlcPath, jstring embedPath, jboolean allowCpu) {
    g_snpe.reset();
    const char *p = env->GetStringUTFChars(dlcPath, nullptr);
    std::string path(p);
    env->ReleaseStringUTFChars(dlcPath, p);
    const char *ep = env->GetStringUTFChars(embedPath, nullptr);
    std::string embed(ep);
    env->ReleaseStringUTFChars(embedPath, ep);

    std::unique_ptr<zdl::DlContainer::IDlContainer> container = zdl::DlContainer::IDlContainer::open(path);
    if (!container) return env->NewStringUTF(("ERROR: cannot open decoder DLC " + path).c_str());

    zdl::DlSystem::RuntimeList list;
    list.add(zdl::DlSystem::Runtime_t::DSP);
    g_snpe = setBuilderOptions(container, zdl::DlSystem::Runtime_t::DSP, list, /*useUserSuppliedBuffers*/ false, /*caching*/ false);
    std::string warn;
    if (!g_snpe) {
        const char *why = "decoder could not be built for the DSP/HTP runtime";
        if (!allowCpu) return env->NewStringUTF((std::string("ERROR: not running on the NPU: ") + why).c_str());
        list.clear();
        list.add(zdl::DlSystem::Runtime_t::CPU);
        g_snpe = setBuilderOptions(container, zdl::DlSystem::Runtime_t::CPU, list, false, false);
        if (!g_snpe) return env->NewStringUTF("ERROR: decoder build failed on DSP and CPU");
        warn = std::string("WARN: CPU FALLBACK - the decoder is NOT running on the NPU: ") + why;
    }

    auto &factory = zdl::SNPE::SNPEFactory::getTensorFactory();
    auto embDims = g_snpe->getInputDimensions("emb");
    auto xaDims = g_snpe->getInputDimensions("xa");
    auto idxDims = g_snpe->getInputDimensions("idx");
    if (!embDims || !xaDims || !idxDims) {
        g_snpe.reset();
        return env->NewStringUTF("ERROR: decoder DLC does not have the inputs emb/xa/idx");
    }
    g_emb = factory.createTensor(*embDims);
    g_xa = factory.createTensor(*xaDims);
    g_idx = factory.createTensor(*idxDims);
    g_dim = (*embDims)[(*embDims).rank() - 1];
    g_len = g_emb->getSize() / g_dim;

    FILE *f = fopen(embed.c_str(), "rb");
    if (!f) { g_snpe.reset(); return env->NewStringUTF(("ERROR: cannot read " + embed).c_str()); }
    fseek(f, 0, SEEK_END);
    long bytes = ftell(f);
    fseek(f, 0, SEEK_SET);
    g_embedTable.assign((size_t) bytes / 2, 0);
    size_t got = fread(g_embedTable.data(), 1, (size_t) bytes, f);
    fclose(f);
    if (got != (size_t) bytes || g_embedTable.size() <= g_len * g_dim) { g_snpe.reset(); return env->NewStringUTF("ERROR: embedding table is truncated"); }
    DLOGI("decoder loaded: L=%zu D=%zu vocab=%zu", g_len, g_dim, g_embedTable.size() / g_dim - g_len);
    return env->NewStringUTF(warn.c_str());
}

// Returns the generated ids (ending with eot when it was produced), or null on error (see lastError()).
extern "C" JNIEXPORT jintArray JNICALL
Java_com_b612p_npubridge_WhisperDecoderNative_decode(JNIEnv *env, jobject, jfloatArray hidden, jintArray prompt,
                                                      jint eot, jint maxNew) {
    g_lastError.clear();
    if (!g_snpe) { g_lastError = "decoder not loaded"; return nullptr; }

    jsize hn = env->GetArrayLength(hidden);
    if ((size_t) hn != g_xa->getSize()) {
        g_lastError = "encoder output has " + std::to_string(hn) + " floats, decoder expects " + std::to_string(g_xa->getSize());
        return nullptr;
    }
    env->GetFloatArrayRegion(hidden, 0, hn, &*g_xa->begin());

    std::vector<jint> ids(env->GetArrayLength(prompt));
    env->GetIntArrayRegion(prompt, 0, (jsize) ids.size(), ids.data());
    std::vector<jint> generated;

    zdl::DlSystem::TensorMap in, out;
    in.add("emb", g_emb.get());
    in.add("xa", g_xa.get());
    in.add("idx", g_idx.get());

    for (int step = 0; step < maxNew; step++) {
        if (ids.size() >= g_len) break;                            // out of positions: stop and let the caller terminate
        std::fill(g_emb->begin(), g_emb->end(), 0.0f);
        const size_t vocab = g_embedTable.size() / g_dim - g_len;
        for (size_t i = 0; i < ids.size(); i++) {
            if ((size_t) ids[i] >= vocab) { g_lastError = "token id out of range"; return nullptr; }
            const uint16_t *pos = &g_embedTable[i * g_dim];
            const uint16_t *tok = &g_embedTable[(g_len + (size_t) ids[i]) * g_dim];
            float *dst = &*g_emb->begin() + i * g_dim;
            for (size_t k = 0; k < g_dim; k++) dst[k] = halfToFloat(tok[k]) + halfToFloat(pos[k]);
        }
        *g_idx->begin() = (float) (ids.size() - 1);

        out.clear();
        if (!g_snpe->execute(in, out)) { g_lastError = "SNPE execute failed in the decoder"; return nullptr; }
        zdl::DlSystem::ITensor *logits = out.getTensor("logits");
        if (!logits) { g_lastError = "decoder produced no logits"; return nullptr; }

        // Greedy. Ids above the end-of-text token are language/task/timestamp markers, never wanted in the text.
        int best = 0;
        float bestV = -1e30f;
        int n = 0;
        for (auto it = logits->cbegin(); it != logits->cend(); ++it, ++n) {
            if (n > eot) break;
            if (*it > bestV) { bestV = *it; best = n; }
        }
        ids.push_back(best);
        generated.push_back(best);
        if (best == eot) break;
    }

    jintArray result = env->NewIntArray((jsize) generated.size());
    env->SetIntArrayRegion(result, 0, (jsize) generated.size(), generated.data());
    return result;
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_b612p_npubridge_WhisperDecoderNative_lastError(JNIEnv *env, jobject) {
    return env->NewStringUTF(g_lastError.c_str());
}

extern "C" JNIEXPORT jint JNICALL
Java_com_b612p_npubridge_WhisperDecoderNative_positions(JNIEnv *, jobject) {
    return (jint) g_len;
}
