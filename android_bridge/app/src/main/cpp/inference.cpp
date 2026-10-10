//============================================================================
// Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
// SPDX-License-Identifier: BSD-3-Clause-Clear
//============================================================================

#include <jni.h>
#include <string>
#include <iostream>

#include <iterator>
#include <unordered_map>
#include <algorithm>
#include <fstream>
#include <cstdlib>
#include <vector>
#include <hpp/inference.h>

#include "android/log.h"

#include "hpp/CheckRuntime.hpp"
#include "hpp/LoadContainer.hpp"
#include "hpp/SetBuilderOptions.hpp"
#include "hpp/LoadInputTensor.hpp"
#include "hpp/CreateUserBuffer.hpp"
#include "hpp/Util.hpp"

std::unique_ptr<zdl::SNPE::SNPE> snpe_dsp;
std::unique_ptr<zdl::SNPE::SNPE> snpe_cpu;
static zdl::DlSystem::Runtime_t runtime = zdl::DlSystem::Runtime_t::CPU;
static zdl::DlSystem::RuntimeList runtimeList;
bool useUserSuppliedBuffers = true;
bool useIntBuffer = false;

std::string dlc_path;

// Default is strict: the encoder must run on the Hexagon DSP/HTP. A CPU build is only made
// when the app explicitly allows it (dev switch), and the caller is then told loudly.
bool g_allow_cpu_fallback = false;

std::string build_network(const uint8_t * dlc_buffer, const size_t dlc_size)
{
    std::string outputLogger;
    bool usingInitCaching = true;

    std::unique_ptr<zdl::DlContainer::IDlContainer> container;

    //loading the model from buffer
    container = loadContainerFromBuffer(dlc_buffer, dlc_size);
    if (container == nullptr) {
        LOGE("Error while opening the container file.");
        return "Error while opening the container file.\n";
    }
    if(runtime != zdl::DlSystem::Runtime_t::UNSET)
    {
        bool ret = runtimeList.add(checkRuntime(runtime));
        if(ret == false){
            LOGE("Cannot set runtime");
            return outputLogger + "Cannot set runtime";
        }
    } else{
        return outputLogger + "\nCannot set runtime";
    }

    runtimeList.clear();


    // Build for DSP runtime ONLY. The original listed {DSP, CPU}, which let SNPE quietly pick the
    // CPU when the DSP could not start. Diagnostics first, so a failure is explainable.
    zdl::DlSystem::Runtime_t runtime_dsp = zdl::DlSystem::Runtime_t::DSP;
    zdl::DlSystem::Runtime_t runtime_cpu = zdl::DlSystem::Runtime_t::CPU;
    bool dspAvailable = zdl::SNPE::SNPEFactory::isRuntimeAvailable(runtime_dsp);
    bool dspUnsignedPd = zdl::SNPE::SNPEFactory::isRuntimeAvailable(
            runtime_dsp, zdl::DlSystem::RuntimeCheckOption_t::UNSIGNEDPD_CHECK);
    LOGI("DSP runtime available=%d unsignedPD=%d", (int) dspAvailable, (int) dspUnsignedPd);

    runtimeList.clear();
    runtimeList.add(runtime_dsp);
    LOGI("BEFORE DSP BUILD ***********************");
    snpe_dsp = setBuilderOptions(container, runtime_dsp, runtimeList, useUserSuppliedBuffers, usingInitCaching);

    if (snpe_dsp == nullptr) {
        LOGE("NPU_ALERT: SNPE could not build the encoder for the DSP runtime");
        std::string why = std::string("DSP/HTP build failed (runtime available=") + (dspAvailable ? "yes" : "no")
                + ", unsignedPD=" + (dspUnsignedPd ? "yes" : "no")
                + "). Check: adb shell setenforce 0 after every reboot, ADSP_LIBRARY_PATH, and that"
                  " libSnpeHtpV75Skel.so is in the app's native library dir.";
        if (!g_allow_cpu_fallback) {
            return "ERROR: not running on the NPU: " + why;
        }
        // Dev-only path: build on CPU so the pipeline can be exercised, and say so.
        runtimeList.clear();
        runtimeList.add(runtime_cpu);
        snpe_dsp = setBuilderOptions(container, runtime_cpu, runtimeList, useUserSuppliedBuffers, usingInitCaching);
        if (snpe_dsp == nullptr) {
            return "ERROR: DSP build failed and the CPU build failed too. " + why;
        }
        LOGE("NPU_ALERT: encoder is running on the CPU (fallback allowed by the app)");
        outputLogger = "WARN: CPU FALLBACK - the encoder is NOT running on the NPU. " + why;
    }
    // Build for CPU runtime
//    runtimeList.clear();
//    runtime = zdl::DlSystem::Runtime_t::CPU;
//    snpe_cpu = setBuilderOptions(container, runtime, runtimeList, useUserSuppliedBuffers, usingInitCaching);

//    if (snpe_cpu == nullptr) {
//        LOGE("SNPE Prepare failed: Builder option failed for CPU runtime");
//        return outputLogger += "CPU Build = Failed ; ";
//    }

//    outputLogger += "CPU Build = OK ; ";
    if (usingInitCaching) {
        if (container->save(dlc_path)) {
            LOGI("Saved container into archive successfully");
//            outputLogger += "\nSaved container cache";
        } else LOGE("Failed to save container into archive");
    }


    return outputLogger;
}

// input vector, runtime
std::string execute_net(std::vector<float *> inputVec, int arrayLength,
                        std::vector<float *>  &outputVec, std::string runtime) {


    bool execStatus;
    // Use the object in place so a failed run does not leave the global null.
    std::unique_ptr<zdl::SNPE::SNPE> &snpe = (runtime == "CPU") ? snpe_cpu : snpe_dsp;
    if (runtime == "CPU") {
        LOGI("Executing on CPU runtime...");
    }

    // do some exception checking
    //Maybe this is a problem for the issue
    if (snpe == nullptr)
        return "Updated SNPE " + runtime + " is NULL ptr";

    zdl::DlSystem::UserBufferMap inputMap, outputMap;

    std::vector <std::unique_ptr<zdl::DlSystem::IUserBuffer>> snpeUserBackedInputBuffers, snpeUserBackedOutputBuffers;
    std::unordered_map <std::string, std::vector<float_t>> applicationOutputBuffers;

    // create UB_TF_N type buffer, if : useIntBuffer=True
    int bitWidth = 32;
    if(useIntBuffer)
        bitWidth = 8;  // set 16 for INT_16 activations

    LOGI("Using UserBuffer with bit-width = %d", bitWidth);

    createOutputBufferMap(outputMap, applicationOutputBuffers, snpeUserBackedOutputBuffers, snpe, useIntBuffer, bitWidth);

    std::unordered_map <std::string, std::vector<float_t>> applicationInputBuffers;
    createInputBufferMap(inputMap, applicationInputBuffers, snpeUserBackedInputBuffers, snpe, useIntBuffer, bitWidth);
//
    if(!loadInputUserBuffer(applicationInputBuffers, snpe, inputVec, arrayLength, inputMap, bitWidth))
        return "\nFailed to load Input UserBuffer";
//
//    // Execute the input buffer map on the model with SNPE
    execStatus = snpe->execute(inputMap, outputMap);
//    // Save the execution results only if successful
    if (execStatus == true) {
        LOGI("SNPE Exec Success !!!");
        // save output tensor
        size_t batchSize = 1;
        if(!saveOutput(outputMap, applicationOutputBuffers, outputVec, batchSize, useIntBuffer, bitWidth))
            return "\nFailed to Save Output Tensor";


    } else return "\nSNPE Execute Failed\n";
//
    return "";
}
