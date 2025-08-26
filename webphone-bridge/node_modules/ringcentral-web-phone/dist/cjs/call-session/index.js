"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const sdp_transform_1 = __importDefault(require("sdp-transform"));
const event_emitter_js_1 = __importDefault(require("../event-emitter.js"));
const request_js_1 = __importDefault(require("../sip-message/outbound/request.js"));
const utils_js_1 = require("../utils.js");
const response_js_1 = __importDefault(require("../sip-message/outbound/response.js"));
class CallSession extends event_emitter_js_1.default {
    webPhone;
    sipMessage;
    localPeer;
    remotePeer;
    rtcPeerConnection;
    _mediaStream;
    audioElement;
    state = "init";
    direction;
    inputDeviceId;
    outputDeviceId;
    reqid = 1;
    sdpVersion = 1;
    constructor(webPhone) {
        super();
        this.webPhone = webPhone;
    }
    get mediaStream() {
        return this._mediaStream;
    }
    set mediaStream(stream) {
        this._mediaStream = stream;
        this.emit("mediaStreamSet", stream);
    }
    // for inbound call, this.sipMessage?.headers["Call-Id"] will be the call id
    // for outbound call, this._callId will be the call id. Once the call session is out of "init" state, this.sipMessage will be set
    _callId = (0, utils_js_1.uuid)();
    get callId() {
        return this.sipMessage?.headers["Call-Id"] ?? this._callId;
    }
    get sessionId() {
        return this.sipMessage?.headers["p-rc-api-ids"].match(/session-id=(s-[0-9a-fz]+?)$/)?.[1];
    }
    get partyId() {
        return this.sipMessage?.headers["p-rc-api-ids"].match(/party-id=(p-[0-9a-fz]+?-\d);/)?.[1];
    }
    get remoteNumber() {
        return (0, utils_js_1.extractNumber)(this.remotePeer);
    }
    get localNumber() {
        return this.localPeer
            ? (0, utils_js_1.extractNumber)(this.localPeer)
            : this.webPhone.sipInfo.username;
    }
    get remoteTag() {
        return (0, utils_js_1.extractTag)(this.remotePeer);
    }
    get localTag() {
        return (0, utils_js_1.extractTag)(this.localPeer);
    }
    get isConference() {
        return this.remotePeer
            ? (0, utils_js_1.extractNumber)(this.remotePeer).startsWith("conf_")
            : false;
    }
    async init() {
        this.rtcPeerConnection = new RTCPeerConnection({
            iceServers: this.webPhone.sipInfo.stunServers?.map((url) => ({
                urls: `stun:${url}`,
            })) ?? [],
        });
        // line below is to make sure that you have the permission to access the microphone
        const tempStream = await navigator.mediaDevices.getUserMedia({
            audio: true,
            video: false,
        });
        tempStream.getTracks().forEach((track) => track.stop()); // 🔥 Stop immediately!
        this.inputDeviceId = await this.webPhone.deviceManager.getInputDeviceId();
        this.mediaStream = await navigator.mediaDevices.getUserMedia({
            video: false,
            audio: { deviceId: { exact: this.inputDeviceId } },
        });
        this.mediaStream.getAudioTracks().forEach((track) => {
            const rtcRtpSender = this.rtcPeerConnection.addTrack(track);
            // ref: https://github.com/ringcentral/ringcentral-web-phone/issues/257
            const params = rtcRtpSender.getParameters();
            if (!params.encodings || params.encodings.length === 0) {
                params.encodings = [{}];
            }
            params.encodings.forEach((encoding) => {
                encoding.priority = "high";
            });
            rtcRtpSender.setParameters(params);
        });
        this.rtcPeerConnection.ontrack = async (event) => {
            const remoteStream = event.streams[0];
            this.audioElement = document.createElement("audio");
            this.audioElement.hidden = true;
            this.audioElement.autoplay = true;
            this.audioElement.srcObject = remoteStream;
            // this code should be run last
            this.outputDeviceId = await this.webPhone.deviceManager
                .getOutputDeviceId();
            if (this.outputDeviceId) {
                this.audioElement.setSinkId(this.outputDeviceId);
            }
        };
    }
    async changeInputDevice(deviceId) {
        this.inputDeviceId = deviceId;
        this.mediaStream?.getAudioTracks().forEach((track) => track.stop());
        this.mediaStream = await navigator.mediaDevices.getUserMedia({
            video: false,
            audio: { deviceId: { exact: deviceId } },
        });
        const newAudioTrack = this.mediaStream.getAudioTracks()[0];
        const sender = this.rtcPeerConnection.getSenders().find((sender) => sender.track?.kind === "audio");
        if (sender) {
            sender.replaceTrack(newAudioTrack);
        }
    }
    async changeOutputDevice(deviceId) {
        this.outputDeviceId = deviceId;
        if (deviceId) {
            await this.audioElement.setSinkId(deviceId);
        }
    }
    async transfer(target) {
        return await this._transfer(`sip:${target}@sip.ringcentral.com`);
    }
    async warmTransfer(target) {
        await this.hold();
        // create a new session and user needs to talk to the target before transfer
        const newSession = await this.webPhone.call(target);
        return {
            // complete the transfer
            complete: async () => {
                await this.completeWarmTransfer(newSession);
            },
            // cancel the transfer
            cancel: async () => {
                await newSession.hangup();
                await this.unhold();
            },
            newSession,
        };
    }
    async completeWarmTransfer(existingSession) {
        const target = existingSession.remoteNumber;
        await this._transfer(`"${target}@sip.ringcentral.com" <sip:${target}@sip.ringcentral.com;transport=wss?Replaces=${existingSession.callId}%3Bto-tag%3D${existingSession.remoteTag}%3Bfrom-tag%3D${existingSession.localTag}>`);
    }
    async hangup() {
        const requestMessage = new request_js_1.default(`BYE sip:${this.webPhone.sipInfo.domain} SIP/2.0`, {
            "Call-Id": this.callId,
            From: this.localPeer,
            To: this.remotePeer,
            Via: `SIP/2.0/WSS ${utils_js_1.fakeDomain};branch=${(0, utils_js_1.branch)()}`,
        });
        await this.webPhone.sipClient.request(requestMessage);
    }
    async startRecording() {
        return await this.sendJsonMessage("startcallrecord");
    }
    async stopRecording() {
        return await this.sendJsonMessage("stopcallrecord");
    }
    async flip(target) {
        const flipResult = await this.sendJsonMessage("callflip", {
            target,
        });
        // note: we can't dispose the call session here
        // otherwise the caller will not be able to talk to the flip target
        // after the flip target answers the call, manually dispose the call session
        // todo: review this part
        return flipResult;
    }
    async park() {
        const parkResult = await this.sendJsonMessage("callpark");
        if (parkResult.code === 0) {
            await this.hangup();
        }
        return parkResult;
    }
    async hold() {
        await this.toggleReceive(false);
    }
    async unhold() {
        await this.toggleReceive(true);
    }
    mute() {
        this.toggleTrack(false);
    }
    unmute() {
        this.toggleTrack(true);
    }
    sendDtmf(tones, duration, interToneGap) {
        for (const sender of this.rtcPeerConnection.getSenders()) {
            if (sender.dtmf?.canInsertDTMF) {
                sender.dtmf?.insertDTMF(tones, duration, interToneGap);
            }
        }
    }
    dispose() {
        this.rtcPeerConnection?.close();
        this.mediaStream?.getTracks().forEach((track) => track.stop());
        if (this.audioElement) {
            this.audioElement.srcObject = null;
        }
        this.state = "disposed";
        this.emit("disposed");
        this.removeAllListeners();
    }
    // for mute/unmute
    toggleTrack(enabled) {
        this.rtcPeerConnection.getSenders().forEach((sender) => {
            if (sender.track) {
                sender.track.enabled = enabled;
            }
        });
    }
    // send re-INVITE.
    // If the call is on hold and you don't want to unhold it, set toReceive to false
    async reInvite(toReceive = true) {
        const offer = await this.rtcPeerConnection.createOffer({
            iceRestart: true,
        });
        await this.rtcPeerConnection.setLocalDescription(offer);
        // wait for ICE gathering to complete
        await new Promise((resolve) => {
            this.rtcPeerConnection.onicecandidate = (event) => {
                if (event.candidate === null) {
                    resolve(true);
                }
            };
            setTimeout(() => resolve(false), 2000);
        });
        let sdp = this.rtcPeerConnection.localDescription.sdp;
        // default value is `a=sendrecv`
        if (!toReceive) {
            sdp = sdp.replace(/a=sendrecv/g, "a=sendonly");
        }
        const requestMessage = new request_js_1.default(`INVITE ${(0, utils_js_1.extractAddress)(this.remotePeer)} SIP/2.0`, {
            "Call-Id": this.callId,
            From: this.localPeer,
            To: this.remotePeer,
            Via: `SIP/2.0/WSS ${utils_js_1.fakeDomain};branch=${(0, utils_js_1.branch)()}`,
            "Content-Type": "application/sdp",
        }, sdp);
        const replyMessage = await this.webPhone.sipClient.request(requestMessage);
        await this.rtcPeerConnection.setRemoteDescription({
            type: "answer",
            sdp: replyMessage.body,
        });
        const ackMessage = new request_js_1.default(`ACK ${(0, utils_js_1.extractAddress)(this.remotePeer)} SIP/2.0`, {
            "Call-Id": this.callId,
            From: this.localPeer,
            To: this.remotePeer,
            Via: replyMessage.headers.Via,
            CSeq: replyMessage.headers.CSeq.replace(" INVITE", " ACK"),
        });
        await this.webPhone.sipClient.reply(ackMessage);
    }
    // handle re-INVITE from SIP server
    async handleReInvite(reInviteMessage) {
        this.sipMessage = reInviteMessage;
        await this.rtcPeerConnection.setRemoteDescription({
            type: "offer",
            sdp: reInviteMessage.body,
        });
        const answer = await this.rtcPeerConnection.createAnswer();
        await this.rtcPeerConnection.setLocalDescription(answer);
        // wait for ICE gathering to complete
        await new Promise((resolve) => {
            this.rtcPeerConnection.onicecandidate = (event) => {
                if (event.candidate === null) {
                    resolve(true);
                }
            };
            setTimeout(() => resolve(false), 2000);
        });
        const newMessage = new response_js_1.default(this.sipMessage, {
            responseCode: 200,
            headers: {
                "Content-Type": "application/sdp",
            },
            body: this.rtcPeerConnection.localDescription.sdp,
        });
        await this.webPhone.sipClient.reply(newMessage);
        // note: no need to wait for the final SIP message (refer to inbound call answer function)
        // because nobody is supposed to proactively invoke this function.
    }
    // for hold/unhold
    // toggle between a=sendrecv and a=sendonly
    async toggleReceive(toReceive) {
        if (!this.rtcPeerConnection?.localDescription) {
            return;
        }
        let sdp = this.rtcPeerConnection.localDescription.sdp;
        // default value is `a=sendrecv`
        if (!toReceive) {
            sdp = sdp.replace(/a=sendrecv/g, "a=sendonly");
        }
        // increase the sdp version
        const res = sdp_transform_1.default.parse(sdp);
        this.sdpVersion = Math.max(this.sdpVersion, res.origin.sessionVersion + 1);
        res.origin.sessionVersion = this.sdpVersion++;
        sdp = sdp_transform_1.default.write(res);
        const requestMessage = new request_js_1.default(`INVITE ${(0, utils_js_1.extractAddress)(this.remotePeer)} SIP/2.0`, {
            "Call-Id": this.callId,
            From: this.localPeer,
            To: this.remotePeer,
            Via: `SIP/2.0/WSS ${utils_js_1.fakeDomain};branch=${(0, utils_js_1.branch)()}`,
            "Content-Type": "application/sdp",
        }, sdp);
        const replyMessage = await this.webPhone.sipClient.request(requestMessage);
        const ackMessage = new request_js_1.default(`ACK ${(0, utils_js_1.extractAddress)(this.remotePeer)} SIP/2.0`, {
            "Call-Id": this.callId,
            From: this.localPeer,
            To: this.remotePeer,
            Via: replyMessage.headers.Via,
            CSeq: replyMessage.headers.CSeq.replace(" INVITE", " ACK"),
        });
        await this.webPhone.sipClient.reply(ackMessage);
    }
    async sendJsonMessage(command, args = {}) {
        const reqid = this.reqid++;
        const jsonBody = JSON.stringify({ request: { reqid, command, ...args } });
        const requestMessage = new request_js_1.default(`INFO sip:${this.webPhone.sipInfo.domain} SIP/2.0`, {
            "Call-Id": this.callId,
            From: this.localPeer,
            To: this.remotePeer,
            Via: `SIP/2.0/WSS ${utils_js_1.fakeDomain};branch=${(0, utils_js_1.branch)()}`,
            "Content-Type": "application/json;charset=utf-8",
        }, jsonBody);
        await this.webPhone.sipClient.request(requestMessage);
        return new Promise((resolve) => {
            const resultHandler = (inboundMessage) => {
                if (!inboundMessage.subject.startsWith("INFO sip:")) {
                    return;
                }
                const response = JSON.parse(inboundMessage.body).response;
                if (!response || response.reqid !== reqid || response.command !== command) {
                    return;
                }
                this.webPhone.sipClient.off("inboundMessage", resultHandler);
                resolve(response.result);
            };
            this.webPhone.sipClient.on("inboundMessage", resultHandler);
        });
    }
    async _transfer(uri) {
        const requestMessage = new request_js_1.default(`REFER ${(0, utils_js_1.extractAddress)(this.remotePeer)} SIP/2.0`, {
            "Call-Id": this.callId,
            From: this.localPeer,
            To: this.remotePeer,
            Via: `SIP/2.0/WSS ${utils_js_1.fakeDomain};branch=${(0, utils_js_1.branch)()}`,
            "Refer-To": uri,
            "Referred-By": `<${(0, utils_js_1.extractAddress)(this.localPeer)}>`,
        });
        await this.webPhone.sipClient.request(requestMessage);
        // wait for the final SIP message
        return new Promise((resolve) => {
            const handler = (inboundMessage) => {
                if (inboundMessage.subject.startsWith("BYE sip:") &&
                    inboundMessage.headers["Call-Id"] === this.callId) {
                    this.webPhone.sipClient.off("inboundMessage", handler);
                    resolve();
                }
            };
            this.webPhone.sipClient.on("inboundMessage", handler);
        });
    }
}
exports.default = CallSession;
