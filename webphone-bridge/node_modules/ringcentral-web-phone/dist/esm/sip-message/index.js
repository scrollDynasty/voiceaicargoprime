import { uuid } from "../utils.js";
class SipMessage {
    static fromString(str) {
        const sipMessage = new SipMessage();
        const [init, ...body] = str.split("\r\n\r\n");
        sipMessage.body = body.join("\r\n\r\n");
        const [subject, ...headers] = init.split("\r\n");
        sipMessage.subject = subject;
        sipMessage.headers = Object.fromEntries(headers.map((line) => line.split(": ")));
        if (sipMessage.headers.To && !sipMessage.headers.To.includes(";tag=")) {
            sipMessage.headers.To += ";tag=" + uuid(); // generate local tag
        }
        return sipMessage;
    }
    subject;
    headers;
    body;
    direction;
    constructor(subject = "", headers = {}, body = "") {
        this.subject = subject;
        this.headers = headers;
        this.body = body
            .trim()
            .split(/[\r\n]+/)
            .join("\r\n");
        if (this.body.length > 0) {
            this.body += "\r\n";
        }
    }
    toString() {
        const r = [
            this.subject,
            ...Object.keys(this.headers).map((key) => `${key}: ${this.headers[key]}`),
            "",
            this.body,
        ].join("\r\n");
        return r;
    }
    get shortString() {
        return `${this.direction} - ${this.subject}`;
    }
}
export default SipMessage;
