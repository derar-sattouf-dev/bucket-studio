import { Tooltip, Typography } from "antd";
import { splitKey } from "../utils/format";

const { Text } = Typography;

/** An S3 key shown as folder (muted) over file name (bold); long names are truncated, the tooltip has the full key. */
export function KeyCell({ objectKey }: { objectKey: string }) {
    const { folder, file } = splitKey(objectKey);
    return (
        <Tooltip title={objectKey}>
            <div style={{ minWidth: 0, maxWidth: "100%", overflow: "hidden" }}>
                {folder && <Text type="secondary" ellipsis style={{ fontSize: 11, display: "block" }}>{folder}/</Text>}
                <Text strong ellipsis style={{ fontSize: 13, display: "block" }}>{file}</Text>
            </div>
        </Tooltip>
    );
}
