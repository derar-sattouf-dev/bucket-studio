import { Typography } from "antd";

const { Text } = Typography;

const EXAMPLE_PATH = "clients/acme/2024/beach.jpg";

/** Shows which group an example key lands in for the chosen depth. */
export function GroupDepthExample({ depth, sourcePrefix }: { depth: number; sourcePrefix: string }) {
    const folders = EXAMPLE_PATH.split("/").slice(0, -1);
    const group = depth > 0 ? folders.slice(0, depth).join("/") : null;
    return (
        <Text type="secondary" style={{ display: "block", fontSize: 11, marginTop: 2 }}>
            For <Text code style={{ fontSize: 11 }}>{sourcePrefix}{EXAMPLE_PATH}</Text>{" "}
            {group
                ? <>the group is <Text code style={{ fontSize: 11 }}>{group}</Text>.</>
                : "images are not grouped (one flat list)."}
            {depth > folders.length && " Keys with fewer folders than the depth are listed without a group."}
        </Text>
    );
}
