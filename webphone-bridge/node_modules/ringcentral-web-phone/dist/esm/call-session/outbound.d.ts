import type WebPhone from "../index.js";
import CallSession from "./index.js";
declare class OutboundCallSession extends CallSession {
    constructor(webPhone: WebPhone, callee: string);
    private callee;
    get remoteNumber(): string;
    call(callerId?: string, options?: {
        headers?: Record<string, string>;
    }): Promise<boolean>;
    cancel(): Promise<void>;
}
export default OutboundCallSession;
