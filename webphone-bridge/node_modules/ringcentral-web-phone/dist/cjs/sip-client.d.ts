import EventEmitter from "./event-emitter.js";
import InboundMessage from "./sip-message/inbound.js";
import type OutboundMessage from "./sip-message/outbound/index.js";
import RequestMessage from "./sip-message/outbound/request.js";
import ResponseMessage from "./sip-message/outbound/response.js";
import type { SipClient, SipClientOptions, SipInfo } from "./types.js";
export declare class DefaultSipClient extends EventEmitter implements SipClient {
    disposed: boolean;
    wsc: WebSocket;
    sipInfo: SipInfo;
    instanceId: string;
    private debug;
    private timeoutHandle;
    constructor(options: SipClientOptions);
    start(): Promise<void>;
    private useBackupOutboundProxy;
    toggleBackupOutboundProxy(enabled?: boolean): void;
    connect(): Promise<void>;
    dispose(): Promise<void>;
    register(expires: number): Promise<void>;
    unregister(): Promise<void>;
    request(message: RequestMessage): Promise<InboundMessage>;
    reply(message: ResponseMessage): Promise<void>;
    send(message: OutboundMessage, waitForReply?: boolean): Promise<InboundMessage>;
}
export declare class DummySipClient extends EventEmitter implements SipClient {
    private static inboundMessage;
    disposed: boolean;
    wsc: WebSocket;
    constructor();
    start(): Promise<void>;
    request(): Promise<InboundMessage>;
    reply(): Promise<void>;
    dispose(): Promise<void>;
}
