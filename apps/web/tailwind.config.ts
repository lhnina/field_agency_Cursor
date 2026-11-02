import type { Config } from "tailwindcss";
import tokens from "./src/design/tokens.json";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        fo: {
          brand: tokens.color.brand.DEFAULT,
          "brand-hover": tokens.color.brand.hover,
          "brand-pressed": tokens.color.brand.pressed,
          "brand-subtle": tokens.color.brand.subtle,
          "brand-muted": tokens.color.brand.muted,
          accent: tokens.color.accent.DEFAULT,
          "accent-hover": tokens.color.accent.hover,
          "accent-subtle": tokens.color.accent.subtle,
          ink: tokens.color.ink.DEFAULT,
          "ink-secondary": tokens.color.ink.secondary,
          "ink-muted": tokens.color.ink.muted,
          canvas: tokens.color.surface.canvas,
          surface: tokens.color.surface.DEFAULT,
          "surface-raised": tokens.color.surface.raised,
          border: tokens.color.border.DEFAULT,
          "border-strong": tokens.color.border.strong,
          "sidebar-bg": tokens.color.sidebar.bg,
          "sidebar-border": tokens.color.sidebar.border,
          success: tokens.color.semantic.success.DEFAULT,
          "success-subtle": tokens.color.semantic.success.subtle,
          warning: tokens.color.semantic.warning.DEFAULT,
          "warning-subtle": tokens.color.semantic.warning.subtle,
          danger: tokens.color.semantic.danger.DEFAULT,
          "danger-subtle": tokens.color.semantic.danger.subtle,
          info: tokens.color.semantic.info.DEFAULT,
          "info-subtle": tokens.color.semantic.info.subtle,
          reposicao: tokens.color.service.reposicao,
          promocao: tokens.color.service.promocao,
          logistica: tokens.color.service.logistica,
          equipas: tokens.color.service.equipas,
          unassigned: tokens.color.service.unassigned,
        },
      },
      fontFamily: {
        sans: tokens.typography.fontFamily.sans,
        mono: tokens.typography.fontFamily.mono,
      },
      borderRadius: {
        fo: tokens.radius.md,
        "fo-sm": tokens.radius.sm,
        "fo-lg": tokens.radius.lg,
      },
      boxShadow: {
        "fo-sm": tokens.shadow.sm,
        "fo-md": tokens.shadow.md,
      },
      width: {
        sidebar: tokens.layout.sidebarWidth,
        drawer: tokens.layout.drawerWidth,
      },
      height: {
        header: tokens.layout.headerHeight,
        btn: tokens.component.buttonHeight,
      },
      transitionDuration: {
        fo: tokens.motion.fast,
      },
    },
  },
  plugins: [],
};

export default config;
