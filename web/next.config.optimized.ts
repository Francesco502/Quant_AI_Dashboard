import type { NextConfig } from "next";

/**
 * 优化版 Next.js 配置 (2核2GB服务器专用)
 *
 * 主要优化：
 * - 静态导出 (output: 'export') - 无需 Node.js 运行时
 * - 图片优化禁用 - 减少构建时间和资源占用
 * - 代码分割优化
 * - 压缩和 tree shaking
 */
const nextConfig: NextConfig = {
  // 静态导出模式 - 生成纯 HTML/CSS/JS，无需 Node 服务器
  output: "export",

  // 静态导出目录
  distDir: "dist",

  // 图片优化配置（静态导出模式下需要禁用）
  images: {
    unoptimized: true,
  },

  // 压缩配置
  compress: true,

  // 构建配置
  poweredByHeader: false, // 隐藏 X-Powered-By 头
  generateEtags: true,

  // 实验性功能（Next.js 14+）
  experimental: {
    // 优化包体积
    optimizePackageImports: [
      "recharts",
      "framer-motion",
      "@radix-ui/react-icons",
    ],
  },

  // 重写规则（静态导出时使用）
  async rewrites() {
    return {
      beforeFiles: [
        // API 请求在静态导出模式下不会被处理
        // 实际部署时由 Nginx 反向代理到后端
      ],
    };
  },

  // 头部配置
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
      {
        source: "/",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=0, must-revalidate",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
