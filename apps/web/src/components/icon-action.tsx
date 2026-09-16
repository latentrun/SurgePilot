import type { ComponentType, SVGProps } from "react";
import { Link } from "react-router-dom";

type IconComponent = ComponentType<SVGProps<SVGSVGElement>>;

const toneClass = {
  primary: "text-primary hover:border-primary/40 hover:bg-primary/10",
  danger: "text-error hover:border-error/40 hover:bg-error/10",
};

const baseClass =
  "inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/[0.03] transition disabled:cursor-not-allowed disabled:opacity-40";

export function IconActionLink({
  Icon,
  label,
  to,
  tone = "primary",
}: {
  Icon: IconComponent;
  label: string;
  to: string;
  tone?: keyof typeof toneClass;
}) {
  return (
    <Link
      aria-label={label}
      className={`${baseClass} ${toneClass[tone]}`}
      title={label}
      to={to}
    >
      <Icon aria-hidden="true" className="h-4 w-4" />
    </Link>
  );
}

export function IconActionButton({
  Icon,
  disabled = false,
  label,
  onClick,
  tone = "primary",
}: {
  Icon: IconComponent;
  disabled?: boolean;
  label: string;
  onClick: () => void;
  tone?: keyof typeof toneClass;
}) {
  return (
    <button
      aria-label={label}
      className={`${baseClass} ${toneClass[tone]}`}
      disabled={disabled}
      onClick={onClick}
      title={label}
      type="button"
    >
      <Icon aria-hidden="true" className="h-4 w-4" />
    </button>
  );
}
