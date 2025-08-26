import type EventEmitter from "./event-emitter.js";
import type InboundMessage from "./sip-message/inbound.js";
import type RequestMessage from "./sip-message/outbound/request.js";
import type ResponseMessage from "./sip-message/outbound/response.js";
export interface SipClientOptions {
    sipInfo: SipInfo;
    instanceId?: string;
    debug?: boolean;
}
export type WebPhoneOptions = SipClientOptions & {
    sipClient?: SipClient;
    deviceManager?: DeviceManager;
    autoAnswer?: boolean;
};
export interface SipInfo {
    authorizationId: string;
    domain: string;
    outboundProxy: string;
    outboundProxyBackup: string;
    username: string;
    password: string;
    stunServers: string[];
}
export type SipClient = EventEmitter & {
    disposed: boolean;
    wsc: WebSocket;
    start: () => Promise<void>;
    request: (message: RequestMessage) => Promise<InboundMessage>;
    reply: (message: ResponseMessage) => Promise<void>;
    dispose: () => Promise<void>;
};
export interface DeviceManager {
    getInputDeviceId: () => Promise<string>;
    getOutputDeviceId: () => Promise<string | undefined>;
}
