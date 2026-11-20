import { Image, Space, Typography } from "antd";
import { IMAGE_FALLBACK, toBrowserUrl } from "../../../utils/storageUrl";

const { Text } = Typography;

/** Files generated next to a published image (thumbnails, WebP copies, …). */
export function DerivativeList({ urls }: { urls: Record<string, string> }) {
    const entries = Object.entries(urls);
    if (entries.length === 0) {
        return <Text type="secondary" style={{ fontSize: 12 }}>No derivatives are configured for publishing.</Text>;
    }
    return (
        <Image.PreviewGroup>
            <Space size={16} wrap>
                {entries.map(([name, url]) => (
                    <figure key={name} style={{ margin: 0, textAlign: "center" }}>
                        <Image src={toBrowserUrl(url) ?? undefined} width={88} height={88} alt={name} fallback={IMAGE_FALLBACK}
                               loading="lazy" decoding="async"
                               style={{ objectFit: "contain", border: "1px solid #e2e8f0", borderRadius: 6, background: "#fff" }} />
                        <figcaption>
                            <a href={toBrowserUrl(url) ?? undefined} target="_blank" rel="noopener noreferrer" style={{ fontSize: 11 }}>
                                {name}
                            </a>
                        </figcaption>
                    </figure>
                ))}
            </Space>
        </Image.PreviewGroup>
    );
}
