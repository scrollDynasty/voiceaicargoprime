import type InboundMessage from "../sip-message/inbound.js";
import type WebPhone from "../index.js";
import CallSession from "./index.js";
import RcMessage from "../rc-message/rc-message.js";
declare class InboundCallSession extends CallSession {
    constructor(webPhone: WebPhone, inviteMessage: InboundMessage);
    get rcApiCallInfo(): {
        callerIdName?: string;
        queueName?: string;
    };
    confirmReceive(): Promise<void>;
    toVoicemail(): Promise<void>;
    decline(): Promise<void>;
    forward(target: string): Promise<void>;
    startReply(): Promise<void>;
    reply(text: string): Promise<RcMessage>;
    answer(): Promise<void>;
    protected sendRcMessage(cmd: number, body?: Record<string | number | symbol, never> | {
        RepTp: string;
        Bdy: string;
    } | {
        FwdDly: string;
        Phn: string;
        PhnTp: string;
    }): Promise<void>;
}
export default InboundCallSession;
