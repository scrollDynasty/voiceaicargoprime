"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.DummySipClient = exports.DefaultSipClient = void 0;
const event_emitter_js_1 = __importDefault(require("./event-emitter.js"));
const rc_message_js_1 = __importDefault(require("./rc-message/rc-message.js"));
const inbound_js_1 = __importDefault(require("./sip-message/inbound.js"));
const request_js_1 = __importDefault(require("./sip-message/outbound/request.js"));
const response_js_1 = __importDefault(require("./sip-message/outbound/response.js"));
const utils_js_1 = require("./utils.js");
const maxExpires = 60;
class DefaultSipClient extends event_emitter_js_1.default {
    disposed = false;
    wsc;
    sipInfo;
    instanceId;
    debug;
    timeoutHandle;
    constructor(options) {
        super();
        this.sipInfo = options.sipInfo;
        this.instanceId = options.instanceId ?? this.sipInfo.authorizationId;
        this.debug = options.debug ?? false;
    }
    async start() {
        await this.connect();
        if (this.timeoutHandle) {
            clearInterval(this.timeoutHandle);
        }
        await this.register(maxExpires);
    }
    useBackupOutboundProxy = false;
    toggleBackupOutboundProxy(enabled = true) {
        this.useBackupOutboundProxy = enabled;
    }
    connect() {
        this.wsc = new WebSocket("wss://" +
            (this.useBackupOutboundProxy
                ? this.sipInfo.outboundProxyBackup
                : this.sipInfo.outboundProxy), "sip");
        if (this.debug) {
            const wscSend = this.wsc.send.bind(this.wsc);
            this.wsc.send = (message) => {
                console.log(`Sending...(${new Date()})\n` + message);
                return wscSend(message);
            };
        }
        this.wsc.addEventListener("message", async (event) => {
            const inboundMessage = inbound_js_1.default.fromString(event.data);
            if (inboundMessage.subject.startsWith("MESSAGE sip:")) {
                const rcMessage = await rc_message_js_1.default.fromXml(inboundMessage.body);
                if (rcMessage.body.Cln &&
                    rcMessage.body.Cln !== this.sipInfo.authorizationId) {
                    return; // the message is not for this instance
                }
            }
            if (this.debug) {
                console.log(`Receiving...(${new Date()})\n` + event.data);
            }
            this.emit("inboundMessage", inboundMessage);
            if (inboundMessage.subject.startsWith("MESSAGE sip:") ||
                inboundMessage.subject.startsWith("BYE sip:") ||
                inboundMessage.subject.startsWith("CANCEL sip:") ||
                inboundMessage.subject.startsWith("INFO sip:") ||
                inboundMessage.subject.startsWith("NOTIFY sip:")) {
                // Auto reply 200 OK to MESSAGE, BYE, CANCEL, INFO, NOTIFY
                await this.reply(new response_js_1.default(inboundMessage, { responseCode: 200 }));
            }
        });
        return new Promise((resolve, reject) => {
            const openEventHandler = () => {
                this.wsc.removeEventListener("open", openEventHandler);
                resolve();
            };
            this.wsc.addEventListener("open", openEventHandler);
            const errorEventHandler = (e) => {
                this.wsc.removeEventListener("error", errorEventHandler);
                reject(e);
            };
            this.wsc.addEventListener("error", errorEventHandler);
        });
    }
    async dispose() {
        this.disposed = true;
        clearInterval(this.timeoutHandle);
        this.removeAllListeners();
        await this.unregister();
        this.wsc.close();
    }
    async register(expires) {
        const requestMessage = new request_js_1.default(`REGISTER sip:${this.sipInfo.domain} SIP/2.0`, {
            "Call-Id": (0, utils_js_1.uuid)(),
            Contact: `<sip:${utils_js_1.fakeEmail};transport=wss>;+sip.instance="<urn:uuid:${this.instanceId}>";expires=${expires}`,
            From: `<sip:${this.sipInfo.username}@${this.sipInfo.domain}>;tag=${(0, utils_js_1.uuid)()}`,
            To: `<sip:${this.sipInfo.username}@${this.sipInfo.domain}>`,
            Via: `SIP/2.0/WSS ${utils_js_1.fakeDomain};branch=${(0, utils_js_1.branch)()}`,
        });
        // if cannot get response in 5 seconds, we close the connection
        const closeHandle = setTimeout(() => this.wsc.close(), 5000);
        let inboundMessage = await this.request(requestMessage);
        clearTimeout(closeHandle);
        const wwwAuth = inboundMessage.headers["Www-Authenticate"] ||
            inboundMessage.headers["WWW-Authenticate"];
        if (wwwAuth) {
            const nonce = wwwAuth.match(/, nonce="(.+?)"/)[1];
            const newMessage = requestMessage.fork();
            newMessage.headers.Authorization = (0, utils_js_1.generateAuthorization)(this.sipInfo, nonce, "REGISTER");
            inboundMessage = await this.request(newMessage);
        }
        else if (inboundMessage.subject.startsWith("SIP/2.0 603 ")) {
            throw new Error("Registration failed: " + inboundMessage.subject);
        }
        if (expires > 0) { // not for unregister
            const serverExpires = Number(inboundMessage.headers.Contact.match(/;expires=(\d+)/)[1]);
            this.timeoutHandle = setTimeout(() => {
                this.register(expires);
            }, (serverExpires - 3) * 1000);
        }
    }
    async unregister() {
        await this.register(0);
    }
    async request(message) {
        return await this.send(message, true);
    }
    async reply(message) {
        await this.send(message, false);
    }
    send(message, waitForReply = false) {
        this.wsc.send(message.toString());
        this.emit("outboundMessage", message);
        if (!waitForReply) {
            return new Promise((resolve) => {
                resolve(new inbound_js_1.default());
            });
        }
        return new Promise((resolve) => {
            const messageListerner = (inboundMessage) => {
                if (inboundMessage.headers.CSeq !== message.headers.CSeq) {
                    return;
                }
                if (inboundMessage.subject.startsWith("SIP/2.0 100 ")) {
                    return; // ignore
                }
                this.off("inboundMessage", messageListerner);
                resolve(inboundMessage);
            };
            this.on("inboundMessage", messageListerner);
        });
    }
}
exports.DefaultSipClient = DefaultSipClient;
// this is for multiple instances with shared worker, dummy phones do not talk to SIP server at all
class DummySipClient extends event_emitter_js_1.default {
    static inboundMessage = new inbound_js_1.default();
    disposed = false;
    wsc;
    constructor() {
        super();
    }
    async start() { }
    request() {
        return Promise.resolve(DummySipClient.inboundMessage);
    }
    async reply() { }
    dispose() {
        this.disposed = true;
        return Promise.resolve();
    }
}
exports.DummySipClient = DummySipClient;
