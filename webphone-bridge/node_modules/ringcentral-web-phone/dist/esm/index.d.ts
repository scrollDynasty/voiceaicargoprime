import OutboundCallSession from "./call-session/outbound.js";
import EventEmitter from "./event-emitter.js";
import type CallSession from "./call-session/index.js";
import type { DeviceManager, SipClient, SipInfo, WebPhoneOptions } from "./types.js";
declare class WebPhone extends EventEmitter {
    sipInfo: SipInfo;
    sipClient: SipClient;
    deviceManager: DeviceManager;
    callSessions: CallSession[];
    autoAnswer: boolean;
    options: WebPhoneOptions;
    disposed: boolean;
    constructor(options: WebPhoneOptions);
    start(): Promise<void>;
    dispose(): Promise<void>;
    call(callee: string, callerId?: string, options?: {
        headers?: Record<string, string>;
    }): Promise<OutboundCallSession>;
}
export default WebPhone;
