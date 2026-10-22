import * as React from "react"
import { cn } from "@/lib/utils"
import {
  formatHands,
  formatStatValue,
  shouldDim,
  shouldShowSample,
} from "@/lib/h2n-format"

export type StatValueFormat = "pct" | "number" | "bb100"
export type StatValueTone = "default" | "pos" | "neg" | "zero" | "muted"

export interface StatValueParts {
  /** Formatted value ("23", "9.5", "--"). */
  text: string
  /** Small trailing sample number, or null when not shown. */
  sampleText: string | null
  /** Draw the value in the subtle text level (low sample or no value). */
  dim: boolean
}

/** Pure display rule for a stat value and its sample size. */
export function statValueParts(
  value: number | null | undefined,
  sample: number | null | undefined,
  format: StatValueFormat = "pct",
): StatValueParts {
  const s = sample ?? null
  let text: string
  if (format === "bb100") text = formatStatValue(value, "bb100", s)
  else if (format === "number") text = formatHands(value)
  else text = formatStatValue(value, "percent", s)
  const noValue = text === "--"
  return {
    text,
    sampleText: !noValue && shouldShowSample(s) ? String(s) : null,
    dim: noValue || shouldDim(s),
  }
}

const toneClass: Record<StatValueTone, string> = {
  default: "",
  pos: "text-money-pos",
  neg: "text-money-neg",
  zero: "text-money-zero",
  muted: "text-muted-foreground",
}

export interface StatValueProps extends Omit<React.ComponentProps<"span">, "children"> {
  value: number | null | undefined
  /** Opportunities behind the value. */
  sample?: number | null
  format?: StatValueFormat
  tone?: StatValueTone
  /** Force the sample to be shown whenever it is above zero. */
  showSample?: boolean
}

export function StatValue({
  value,
  sample,
  format = "pct",
  tone = "default",
  showSample,
  className,
  ...props
}: StatValueProps) {
  const parts = statValueParts(value, sample, format)
  const sampleText =
    parts.sampleText ?? (showSample && sample != null && sample > 0 && parts.text !== "--" ? String(sample) : null)
  return (
    <span
      data-slot="stat-value"
      data-sample={sample ?? undefined}
      className={cn("tabular-nums", parts.dim ? "text-subtle-foreground" : toneClass[tone], className)}
      {...props}
    >
      {parts.text}
      {sampleText !== null && (
        <>
          <span aria-hidden className="ml-0.5 align-sub text-2xs text-sample">
            {sampleText}
          </span>
          <span className="sr-only"> (n={sampleText})</span>
        </>
      )}
    </span>
  )
}
