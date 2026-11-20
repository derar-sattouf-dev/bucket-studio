import { Suspense } from "react";
import { Button, Divider, Layout, Menu, Typography } from "antd";
import { LogoutOutlined } from "@ant-design/icons";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { BrandLogo } from "../components/BrandLogo";
import { PageLoader } from "../components/PageLoader";
import { APP_NAME } from "../constants/app";
import { IMAGES_GROUP_KEY, buildNavItems } from "./navigation";
import { SIDEBAR_BG } from "./theme";

const { Sider, Content } = Layout;
const { Text, Title } = Typography;

/** Authenticated shell: sidebar navigation + lazily loaded page content. */
export function AppLayout() {
    const navigate = useNavigate();
    const { pathname, search } = useLocation();
    const { isAdmin, currentUser, logout } = useAuth();

    const onImagesPage = pathname === "/images";
    const statusFilter = new URLSearchParams(search).get("status");
    const imagesKey = statusFilter ? `/images?status=${statusFilter}` : IMAGES_GROUP_KEY;
    const selectedKey = onImagesPage ? imagesKey : pathname;
    const openKeys = onImagesPage ? [IMAGES_GROUP_KEY] : [];
    const navItems = buildNavItems({ isAdmin, onImagesTitleClick: () => navigate("/images") });

    const handleLogout = () => {
        logout();
        navigate("/login");
    };

    return (
        <Layout style={{ minHeight: "100vh" }}>
            <Sider width={220} style={{ background: SIDEBAR_BG, display: "flex", flexDirection: "column" }}>
                <div style={{ padding: "20px 16px 8px", display: "flex", alignItems: "center", gap: 10 }}>
                    <BrandLogo size={28} />
                    <Title level={5} style={{ color: "#fff", margin: 0 }}>{APP_NAME}</Title>
                </div>
                <div style={{ overflowY: "auto", flex: 1 }}>
                    <Menu
                        theme="dark"
                        mode="inline"
                        selectedKeys={[selectedKey]}
                        openKeys={openKeys}
                        // Internal items are keyed by path; others (e.g. the external Help link) handle themselves.
                        onClick={({ key }) => { if (key.startsWith("/")) navigate(key); }}
                        items={navItems}
                        style={{ background: "transparent" }}
                    />
                </div>
                <div style={{ padding: "12px 16px 20px" }}>
                    <Divider style={{ borderColor: "#ffffff15", margin: "0 0 12px" }} />
                    {currentUser && (
                        <Text style={{ display: "block", color: "#ffffffa0", fontSize: 12, marginBottom: 8 }}>
                            Signed in as <strong style={{ color: "#fff" }}>{currentUser.username}</strong>
                            {isAdmin && " (admin)"}
                        </Text>
                    )}
                    <Button
                        icon={<LogoutOutlined />}
                        onClick={handleLogout}
                        style={{ width: "100%", background: "transparent", color: "#fff", borderColor: "#ffffff30" }}
                    >
                        Sign out
                    </Button>
                </div>
            </Sider>
            <Layout>
                <Content style={{ background: "#f8fafc", minHeight: "100vh" }}>
                    <Suspense fallback={<PageLoader />}>
                        <Outlet />
                    </Suspense>
                </Content>
            </Layout>
        </Layout>
    );
}
