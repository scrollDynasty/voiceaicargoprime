"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const request_js_1 = __importDefault(require("../sip-message/outbound/request.js"));
const response_js_1 = __importDefault(require("../sip-message/outbound/response.js"));
const index_js_1 = __importDefault(require("./index.js"));
const utils_js_1 = require("../utils.js");
const rc_message_js_1 = __importDefault(require("../rc-message/rc-message.js"));
const call_control_commands_js_1 = __importDefault(require("../rc-message/call-control-commands.js"));
class InboundCallSession extends index_js_1.default {
    constructor(webPhone, inviteMessage) {
        super(webPhone);
        this.sipMessage = inviteMessage;
        this.localPeer = inviteMessage.headers.To;
        this.remotePeer = inviteMessage.headers.From;
        this.direction = "inbound";
        this.state = "ringing";
        this.emit("ringing");
    }
    // for inbound calls from call queue, there will be p-rc-api-call-info header:
    // p-rc-api-call-info: callAttributes=queue-call,reject;callerIdName=WIRELESS CALLER;displayInfo=queueName;displayInfoSub=callerIdName;queueName=Tyler's call queue
    get rcApiCallInfo() {
        return Object.fromEntries(this.sipMessage.headers["p-rc-api-call-info"]
            .split(";")
            .map((pair) => pair.trim())
            .filter(Boolean)
            .map((pair) => {
            const [key, ...rest] = pair.split("=");
            return [key, rest.join("=")]; // Handles '=' in value
        }));
    }
    async confirmReceive() {
        await this.sendRcMessage(call_control_commands_js_1.default.ClientReceiveConfirm);
    }
    async toVoicemail() {
        await this.sendRcMessage(call_control_commands_js_1.default.ClientVoicemail);
        // wait for outbound reply to CANCEL
        return new Promise((resolve) => {
            const handler = (outboundMessage) => {
                if (outboundMessage.headers["Call-Id"] === this.callId &&
                    outboundMessage.headers.CSeq.endsWith(" CANCEL")) {
                    this.webPhone.sipClient.off("outboundMessage", handler);
                    resolve();
                }
            };
            this.webPhone.sipClient.on("outboundMessage", handler);
        });
    }
    async decline() {
        await this.sendRcMessage(call_control_commands_js_1.default.ClientReject);
        // wait for outbound reply to CANCEL
        return new Promise((resolve) => {
            const handler = (outboundMessage) => {
                if (outboundMessage.headers["Call-Id"] === this.callId &&
                    outboundMessage.headers.CSeq.endsWith(" CANCEL")) {
                    this.webPhone.sipClient.off("outboundMessage", handler);
                    resolve();
                }
            };
            this.webPhone.sipClient.on("outboundMessage", handler);
        });
    }
    async forward(target) {
        await this.sendRcMessage(call_control_commands_js_1.default.ClientForward, {
            FwdDly: "0",
            Phn: target,
            PhnTp: "3",
        });
        // wait for the final SIP message
        return new Promise((resolve) => {
            const handler = (inboundMessage) => {
                if (inboundMessage.subject.startsWith("CANCEL sip:")) {
                    this.webPhone.sipClient.off("inboundMessage", handler);
                    resolve();
                }
            };
            this.webPhone.sipClient.on("inboundMessage", handler);
        });
    }
    async startReply() {
        await this.sendRcMessage(call_control_commands_js_1.default.ClientStartReply);
    }
    async reply(text) {
        await this.sendRcMessage(call_control_commands_js_1.default.ClientReply, {
            RepTp: "0",
            Bdy: text,
        });
        return new Promise((resolve) => {
            const sessionCloseHandler = async (inboundMessage) => {
                if (inboundMessage.subject.startsWith("MESSAGE sip:")) {
                    const rcMessage = await rc_message_js_1.default.fromXml(inboundMessage.body);
                    if (rcMessage.headers.Cmd ===
                        call_control_commands_js_1.default.SessionClose.toString()) {
                        this.webPhone.sipClient.off("inboundMessage", sessionCloseHandler);
                        resolve(rcMessage);
                        // no need to dispose session here, session will dispose unpon CANCEL or BYE
                    }
                }
            };
            this.webPhone.sipClient.on("inboundMessage", sessionCloseHandler);
        });
    }
    async answer() {
        await this.init();
        await this.rtcPeerConnection.setRemoteDescription({
            type: "offer",
            sdp: this.sipMessage.body,
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
        this.state = "answered";
        this.emit("answered");
        // wait for the final SIP message
        return new Promise((resolve) => {
            const handler = async (inboundMessage) => {
                if (inboundMessage.subject.startsWith("MESSAGE sip:")) {
                    const rcMessage = await rc_message_js_1.default.fromXml(inboundMessage.body);
                    if (rcMessage.headers.Cmd ===
                        call_control_commands_js_1.default.AlreadyProcessed.toString()) {
                        this.webPhone.sipClient.off("inboundMessage", handler);
                        resolve();
                    }
                }
            };
            this.webPhone.sipClient.on("inboundMessage", handler);
        });
    }
    async sendRcMessage(cmd, body = {}) {
        if (!this.sipMessage.headers["P-rc"]) {
            return;
        }
        const rcMessage = await rc_message_js_1.default.fromXml(this.sipMessage.headers["P-rc"]);
        const newRcMessage = new rc_message_js_1.default({
            SID: rcMessage.headers.SID,
            Req: rcMessage.headers.Req,
            From: rcMessage.headers.To,
            To: rcMessage.headers.From,
            Cmd: cmd.toString(),
        }, {
            Cln: this.webPhone.sipInfo.authorizationId,
            ...body,
        });
        const requestSipMessage = new request_js_1.default(`MESSAGE sip:${newRcMessage.headers.To} SIP/2.0`, {
            Via: `SIP/2.0/WSS ${utils_js_1.fakeDomain};branch=${(0, utils_js_1.branch)()}`,
            To: `<sip:${newRcMessage.headers.To}>`,
            From: `<sip:${this.webPhone.sipInfo.username}@${this.webPhone.sipInfo.domain}>;tag=${(0, utils_js_1.uuid)()}`,
            "Call-Id": this.callId,
            "Content-Type": "x-rc/agent",
        }, newRcMessage.toXml());
        await this.webPhone.sipClient.request(requestSipMessage);
    }
}
exports.default = InboundCallSession;
