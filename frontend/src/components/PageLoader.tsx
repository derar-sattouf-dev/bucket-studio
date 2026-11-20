import { Spin } from "antd";

/** Full-height spinner used as the Suspense fallback for lazy routes. */
export function PageLoader() {
    return (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
            <Spin size="large" />
        </div>
    );
}

/** Centered spinner for pages that are loading their initial data. */
export function SectionLoader() {
    return <div style={{ padding: 48, textAlign: "center" }}><Spin size="large" /></div>;
}
