import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

export type ChipTone =
  | "neutral" | "accent" | "pos" | "neg"
  | "tag1" | "tag2" | "tag3" | "tag4" | "tag5" | "tag6" | "tag7" | "tag8" | "tag9"

/** Tone to surface/text classes (literal strings so Tailwind can see them). */
export const chipToneClasses: Record<ChipTone, string> = {
  neutral: "bg-muted text-foreground",
  accent: "bg-primary/15 text-primary",
  pos: "bg-money-pos/15 text-money-pos",
  neg: "bg-money-neg/15 text-money-neg",
  tag1: "bg-tag-1/20 text-foreground",
  tag2: "bg-tag-2/20 text-foreground",
  tag3: "bg-tag-3/20 text-foreground",
  tag4: "bg-tag-4/20 text-foreground",
  tag5: "bg-tag-5/20 text-foreground",
  tag6: "bg-tag-6/20 text-foreground",
  tag7: "bg-tag-7/20 text-foreground",
  tag8: "bg-tag-8/20 text-foreground",
  tag9: "bg-tag-9/20 text-foreground",
}

/** Tone to leading-dot colour. */
export const chipDotClasses: Record<ChipTone, string> = {
  neutral: "bg-muted-foreground",
  accent: "bg-primary",
  pos: "bg-money-pos",
  neg: "bg-money-neg",
  tag1: "bg-tag-1",
  tag2: "bg-tag-2",
  tag3: "bg-tag-3",
  tag4: "bg-tag-4",
  tag5: "bg-tag-5",
  tag6: "bg-tag-6",
  tag7: "bg-tag-7",
  tag8: "bg-tag-8",
  tag9: "bg-tag-9",
}

const chipVariants = cva(
  "inline-flex w-fit shrink-0 items-center gap-1 rounded-pill whitespace-nowrap [&_svg]:shrink-0",
  {
    variants: {
      tone: chipToneClasses,
      size: {
        sm: "h-5 px-1.5 text-2xs",
        md: "h-6 px-2 text-xs",
      },
    },
    defaultVariants: { tone: "neutral", size: "md" },
  },
)

export interface ChipProps
  extends Omit<React.ComponentProps<"span">, "onClick" | "children">,
    VariantProps<typeof chipVariants> {
  children?: React.ReactNode
  /** Leading dot, coloured from the tone. */
  dot?: boolean
  icon?: React.ReactNode
  /** Marks a value that differs from its default (small amber dot). */
  nonDefault?: boolean
  /** Makes the chip itself a focusable button. */
  onClick?: React.MouseEventHandler<HTMLButtonElement>
  /** Adds a trailing remove button. */
  onRemove?: () => void
  removeLabel?: string
}

export function Chip({
  tone = "neutral",
  size,
  dot,
  icon,
  nonDefault,
  onClick,
  onRemove,
  removeLabel,
  className,
  children,
  ...props
}: ChipProps) {
  const resolvedTone = tone ?? "neutral"
  const content = (
    <>
      {dot && <span aria-hidden className={cn("size-1.5 rounded-pill", chipDotClasses[resolvedTone])} />}
      {icon}
      {children}
      {nonDefault && (
        <>
          <span aria-hidden className="size-1.5 rounded-pill bg-primary" />
          <span className="sr-only"> (changed)</span>
        </>
      )}
    </>
  )

  const onKeyDown = onRemove
    ? (e: React.KeyboardEvent<HTMLButtonElement>) => {
        if (e.key === "Backspace" || e.key === "Delete") {
          e.preventDefault()
          onRemove()
        }
      }
    : undefined

  const label =
    removeLabel ?? `Remove ${typeof children === "string" || typeof children === "number" ? children : "item"}`

  return (
    <span
      data-slot="chip"
      className={cn(chipVariants({ tone, size }), onRemove && "pr-0.5", className)}
      {...props}
    >
      {onClick ? (
        <button
          type="button"
          onClick={onClick}
          onKeyDown={onKeyDown}
          className="inline-flex h-full items-center gap-1 rounded-pill outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {content}
        </button>
      ) : (
        content
      )}
      {onRemove && (
        <button
          type="button"
          aria-label={label}
          onClick={onRemove}
          className="inline-flex size-4 items-center justify-center rounded-pill opacity-70 outline-none hover:bg-overlay-selected hover:opacity-100 focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X className="size-3" />
        </button>
      )}
    </span>
  )
}

export { chipVariants }
