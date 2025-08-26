"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const mixpanel_browser_1 = __importDefault(require("mixpanel-browser"));
const response_js_1 = __importDefault(require("./sip-message/outbound/response.js"));
const inbound_js_1 = __importDefault(require("./call-session/inbound.js"));
const outbound_js_1 = __importDefault(require("./call-session/outbound.js"));
const event_emitter_js_1 = __importDefault(require("./event-emitter.js"));
const sip_client_js_1 = require("./sip-client.js");
const device_manager_js_1 = require("./device-manager.js");
mixpanel_browser_1.default.init("8d34a0fbc54a5560463ea7b72f235629", { autocapture: false });
class WebPhone extends event_emitter_js_1.default {
    sipInfo;
    sipClient;
    deviceManager;
    callSessions = [];
    autoAnswer = false;
    options;
    disposed = false;
    constructor(options) {
        mixpanel_browser_1.default.identify(options.sipInfo.username);
        mixpanel_browser_1.default.track("init", {
            distinct_id: options.sipInfo.username,
            version: "2.2.3",
        });
        super();
        this.options = options;
        this.sipInfo = options.sipInfo;
        this.sipClient = options.sipClient ?? new sip_client_js_1.DefaultSipClient(options);
        this.deviceManager = options.deviceManager ?? new device_manager_js_1.DefaultDeviceManager();
        this.autoAnswer = options.autoAnswer ?? false;
        this.sipClient.on("inboundMessage", async (inboundMessage) => {
            // either inbound BYE/CANCEL or server reply to outbound BYE/CANCEL
            if (inboundMessage.headers.CSeq.endsWith(" BYE") ||
                inboundMessage.headers.CSeq.endsWith(" CANCEL")) {
                const index = this.callSessions.findIndex((callSession) => callSession.callId === inboundMessage.headers["Call-Id"]);
                if (index !== -1) {
                    const callSession = this.callSessions[index];
                    this.callSessions.splice(index, 1);
                    callSession.dispose();
                }
            }
            // listen for incoming calls
            if (!inboundMessage.subject.startsWith("INVITE sip:")) {
                return;
            }
            // re-INVITE
            const callSession = this.callSessions.find((callSession) => {
                return callSession.callId === inboundMessage.headers["Call-Id"] &&
                    callSession.localPeer === inboundMessage.headers.To &&
                    callSession.remotePeer === inboundMessage.headers.From;
            });
            if (callSession) {
                callSession.handleReInvite(inboundMessage);
                return;
            }
            this.callSessions.push(new inbound_js_1.default(this, inboundMessage));
            // write it this way so that it will be compatible with manate, inboundCallSession will be managed
            const inboundCallSession = this
                .callSessions[this.callSessions.length - 1];
            this.emit("inboundCall", inboundCallSession);
            // tell SIP server that we are ringing
            let tempMesage = new response_js_1.default(inboundMessage, {
                responseCode: 100,
            });
            await this.sipClient.reply(tempMesage);
            tempMesage = new response_js_1.default(inboundMessage, { responseCode: 180 });
            await this.sipClient.reply(tempMesage);
            // if we don't send this, toVoicemail() will not work
            await inboundCallSession.confirmReceive();
            // auto answer
            if (!this.autoAnswer) {
                return;
            }
            if (inboundCallSession.sipMessage.headers["Alert-Info"] !== "Auto Answer") {
                return;
            }
            let delay = 0;
            const callInfoHeader = inboundCallSession.sipMessage.headers["Call-Info"];
            if (callInfoHeader) {
                const match = callInfoHeader.match(/Answer-After=(\d+)/);
                if (match) {
                    delay = parseInt(match[1], 10); // Convert the captured value to an integer
                }
            }
            setTimeout(() => {
                inboundCallSession.answer();
            }, delay);
        });
    }
    async start() {
        await this.sipClient.start();
    }
    async dispose() {
        this.disposed = true;
        // properly dispose all call sessions
        for (const callSession of this.callSessions) {
            if (callSession.state === "answered") {
                await callSession.hangup();
            }
            else if (callSession.direction === "inbound") {
                await callSession.decline();
            }
            else {
                await callSession.cancel();
            }
            // callSession.dispose() will be auto triggered by the above methods
        }
        this.removeAllListeners();
        await this.sipClient.dispose();
    }
    // make an outbound call
    async call(callee, callerId, options) {
        this.callSessions.push(new outbound_js_1.default(this, callee));
        // write it this way so that it will be compatible with manate, outboundCallSession will be managed
        const outboundCallSession = this
            .callSessions[this.callSessions.length - 1];
        this.emit("outboundCall", outboundCallSession);
        await outboundCallSession.init();
        await outboundCallSession.call(callerId, options);
        return outboundCallSession;
    }
}
exports.default = WebPhone;
