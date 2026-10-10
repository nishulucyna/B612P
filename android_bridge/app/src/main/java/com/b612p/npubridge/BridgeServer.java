package com.b612p.npubridge;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.DataInputStream;
import java.io.IOException;
import java.util.Map;

import fi.iki.elonen.NanoHTTPD;

/**
 * Loopback HTTP server the host reaches through `adb forward tcp:8080 tcp:8080`.
 *
 *   GET  /health  200 when both engines are ready, else 503 (JSON with details)
 *   POST /stt     body: WAV bytes            -> {"transcript": "..."}
 *   POST /llm     body: {"prompt": "..."}    -> text/plain raw model output
 *
 * Bound to 127.0.0.1 only; nothing is reachable from the network.
 */
public class BridgeServer extends NanoHTTPD {
    public static final int PORT = 8080;
    private static final int MAX_BODY_BYTES = 32 * 1024 * 1024;

    private final SttEngine stt;
    private final LlmEngine llm;
    private final Object inferenceLock = new Object(); // one NPU job at a time

    public BridgeServer(SttEngine stt, LlmEngine llm) {
        super("127.0.0.1", PORT);
        this.stt = stt;
        this.llm = llm;
    }

    @Override
    public Response serve(IHTTPSession session) {
        String uri = session.getUri();
        Method method = session.getMethod();
        try {
            if (method == Method.GET && "/health".equals(uri)) {
                return health();
            }
            if (method == Method.POST && "/stt".equals(uri)) {
                return handleStt(session);
            }
            if (method == Method.POST && "/llm".equals(uri)) {
                return handleLlm(session);
            }
            return json(Response.Status.NOT_FOUND, error("unknown route " + method + " " + uri));
        } catch (BadRequest e) {
            return json(Response.Status.BAD_REQUEST, error(e.getMessage()));
        } catch (Exception e) {
            return json(Response.Status.INTERNAL_ERROR, error(e.toString()));
        }
    }

    private Response health() throws JSONException {
        boolean ready = stt.isReady() && llm.isReady();
        JSONObject o = new JSONObject();
        o.put("ready", ready);
        o.put("stt_ready", stt.isReady());
        o.put("llm_ready", llm.isReady());
        o.put("stt", stt.status());
        o.put("llm", llm.status());
        return json(ready ? Response.Status.OK : Response.Status.SERVICE_UNAVAILABLE, o);
    }

    private Response handleStt(IHTTPSession session) throws Exception {
        if (!stt.isReady()) {
            return json(Response.Status.SERVICE_UNAVAILABLE, error(stt.status()));
        }
        byte[] wav = readBody(session);
        if (wav.length == 0) {
            throw new BadRequest("empty audio body");
        }
        String transcript;
        synchronized (inferenceLock) {
            transcript = stt.transcribe(wav);
        }
        JSONObject o = new JSONObject();
        o.put("transcript", transcript);
        return json(Response.Status.OK, o);
    }

    private Response handleLlm(IHTTPSession session) throws Exception {
        if (!llm.isReady()) {
            return json(Response.Status.SERVICE_UNAVAILABLE, error(llm.status()));
        }
        String prompt;
        try {
            prompt = new JSONObject(new String(readBody(session), "UTF-8")).getString("prompt");
        } catch (JSONException e) {
            throw new BadRequest("body must be JSON with a \"prompt\" string");
        }
        String output;
        synchronized (inferenceLock) {
            output = llm.generate(prompt);
        }
        return newFixedLengthResponse(Response.Status.OK, "text/plain; charset=utf-8", output);
    }

    private byte[] readBody(IHTTPSession session) throws IOException, BadRequest {
        Map<String, String> headers = session.getHeaders(); // keys are lower-cased
        String lenStr = headers.get("content-length");
        if (lenStr == null) {
            throw new BadRequest("Content-Length required");
        }
        int len;
        try {
            len = Integer.parseInt(lenStr.trim());
        } catch (NumberFormatException e) {
            throw new BadRequest("bad Content-Length");
        }
        if (len < 0 || len > MAX_BODY_BYTES) {
            throw new BadRequest("body too large (max " + MAX_BODY_BYTES + " bytes)");
        }
        byte[] buf = new byte[len];
        new DataInputStream(session.getInputStream()).readFully(buf);
        return buf;
    }

    private static JSONObject error(String message) {
        JSONObject o = new JSONObject();
        try {
            o.put("error", message);
        } catch (JSONException ignored) {
            // key is a constant string; cannot fail
        }
        return o;
    }

    private static Response json(Response.Status status, JSONObject body) {
        return newFixedLengthResponse(status, "application/json; charset=utf-8", body.toString());
    }

    private static final class BadRequest extends Exception {
        BadRequest(String message) {
            super(message);
        }
    }
}
