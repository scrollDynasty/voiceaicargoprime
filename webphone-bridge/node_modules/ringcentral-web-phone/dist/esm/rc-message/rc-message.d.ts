export interface HDR {
    [key: string]: string | undefined;
}
export interface BDY {
    [key: string]: string | undefined;
}
declare class RcMessage {
    private static xmlOptions;
    static fromXml(_xmlStr: string): RcMessage;
    headers: HDR;
    body: BDY;
    constructor(headers: HDR, body: BDY);
    toXml(): any;
}
export default RcMessage;
