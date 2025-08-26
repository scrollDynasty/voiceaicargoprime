import { XMLBuilder, XMLParser } from "fast-xml-parser";
class RcMessage {
    static xmlOptions = {
        ignoreAttributes: false,
        attributeNamePrefix: "",
        attributesGroupName: "$",
        format: false,
        suppressEmptyNode: true,
    };
    static fromXml(_xmlStr) {
        let xmlStr = _xmlStr;
        if (xmlStr.startsWith("P-rc: ")) {
            xmlStr = xmlStr.substring(6);
        }
        const parser = new XMLParser(RcMessage.xmlOptions);
        const parsed = parser.parse(xmlStr);
        return new RcMessage(parsed.Msg.Hdr.$, parsed.Msg.Bdy.$);
    }
    headers;
    body;
    constructor(headers, body) {
        this.headers = headers;
        this.body = body;
    }
    toXml() {
        const builder = new XMLBuilder(RcMessage.xmlOptions);
        const obj = {
            Msg: {
                Hdr: {
                    $: this.headers,
                },
                Bdy: {
                    $: this.body,
                },
            },
        };
        return builder.build(obj);
    }
}
export default RcMessage;
