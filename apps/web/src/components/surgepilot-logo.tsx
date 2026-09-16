import logoUrl from "../assets/logo/surgepilot-logo.svg";

type SurgePilotLogoVariant = "full" | "app-icon";

type SurgePilotLogoProps = Readonly<{
  decorative?: boolean;
  className?: string;
  variant?: SurgePilotLogoVariant;
}>;

const variantClassName: Record<SurgePilotLogoVariant, string> = {
  full: "h-10 w-10",
  "app-icon": "h-9 w-9 rounded-lg",
};

export function SurgePilotLogo({
  className,
  decorative = false,
  variant = "app-icon",
}: SurgePilotLogoProps) {
  return (
    <img
      alt={decorative ? "" : "SurgePilot logo"}
      aria-hidden={decorative ? true : undefined}
      className={className ?? variantClassName[variant]}
      src={logoUrl}
    />
  );
}
