declare class SipMessage {
    static fromString(str: string): SipMessage;
    subject: string;
    headers: {
        [key: string]: string;
    };
    body: string;
    direction: "inbound" | "outbound";
    constructor(subject?: string, headers?: {}, body?: string);
    toString(): string;
    get shortString(): string;
}
export default SipMessage;
