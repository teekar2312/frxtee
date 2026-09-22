import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const eslintConfig = [...nextCoreWebVitals, ...nextTypescript, {
  rules: {
    // Allow `any` in trading data (dynamic API responses)
    "@typescript-eslint/no-explicit-any": "off",
    // Warn on unused vars (not error — some are used in JSX)
    "@typescript-eslint/no-unused-vars": "warn",
    // Keep these off (framework noise)
    "@typescript-eslint/no-non-null-assertion": "off",
    "@typescript-eslint/ban-ts-comment": "off",
    // Enforce no console.log in production code
    "no-console": ["warn", { allow: ["warn", "error"] }],
    // Enforce prefer-const
    "prefer-const": "warn",
    // No debugger in production
    "no-debugger": "error",
    // No unreachable code
    "no-unreachable": "error",
    // React hooks deps should be checked
    "react-hooks/exhaustive-deps": "warn",
    // Allow impure functions in useMemo (shadcn sidebar uses Math.random)
    "react-hooks/purity": "off",
  },
}, {
  ignores: [
    "node_modules/**", ".next/**", "out/**", "build/**", "next-env.d.ts",
    "src/components/ui/**",  // shadcn/ui generated components
    "src/hooks/**",  // shadcn hooks (use-toast, use-mobile)
    "skills/**",  // Z.ai skill scripts (not part of trading app)
  ],
}];

export default eslintConfig;
