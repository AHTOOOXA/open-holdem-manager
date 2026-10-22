import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"
import { Tabs as TabsPrimitive } from "radix-ui"
import { Ellipsis } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

type TabsVariant = "default" | "line"

const TabsValueContext = React.createContext<{
  value: string | undefined
  setValue: (v: string) => void
}>({ value: undefined, setValue: () => {} })

const TabsVariantContext = React.createContext<TabsVariant>("default")

/**
 * Which tabs fit. `widths` include inter-tab gaps. Tabs fill from the left; the
 * "more" button is reserved only when something is hidden; the active tab is
 * swapped in for the last visible one(s) when it would otherwise be hidden.
 */
export function computeVisibleTabs(
  widths: number[],
  available: number,
  moreWidth: number,
  activeIndex: number,
): { visible: number[]; hidden: number[] } {
  const all = widths.map((_, i) => i)
  const total = widths.reduce((a, b) => a + b, 0)
  if (total <= available) return { visible: all, hidden: [] }

  const budget = Math.max(0, available - moreWidth)
  const visible: number[] = []
  let used = 0
  for (let i = 0; i < widths.length; i++) {
    if (used + widths[i] > budget) break
    visible.push(i)
    used += widths[i]
  }
  const hasActive = activeIndex >= 0 && activeIndex < widths.length
  if (hasActive && !visible.includes(activeIndex)) {
    used += widths[activeIndex]
    while (visible.length > 0 && used > budget) {
      used -= widths[visible.pop() as number]
    }
    visible.push(activeIndex)
  }
  return { visible, hidden: all.filter((i) => !visible.includes(i)) }
}

function Tabs({
  className,
  orientation = "horizontal",
  value: valueProp,
  defaultValue,
  onValueChange,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Root>) {
  const [internal, setInternal] = React.useState(defaultValue)
  const value = valueProp ?? internal
  const setValue = React.useCallback(
    (v: string) => {
      setInternal(v)
      onValueChange?.(v)
    },
    [onValueChange]
  )
  const ctx = React.useMemo(() => ({ value, setValue }), [value, setValue])
  return (
    <TabsValueContext.Provider value={ctx}>
      <TabsPrimitive.Root
        data-slot="tabs"
        data-orientation={orientation}
        orientation={orientation}
        value={value}
        onValueChange={setValue}
        className={cn(
          "group/tabs flex gap-2 data-[orientation=horizontal]:flex-col",
          className
        )}
        {...props}
      />
    </TabsValueContext.Provider>
  )
}

const tabsListVariants = cva(
  "group/tabs-list inline-flex w-fit items-center justify-center text-muted-foreground group-data-[orientation=vertical]/tabs:h-fit group-data-[orientation=vertical]/tabs:flex-col",
  {
    variants: {
      variant: {
        default:
          "rounded-lg bg-muted p-[3px] group-data-[orientation=horizontal]/tabs:h-9",
        line:
          "w-full min-w-0 justify-start gap-1 rounded-none border-b border-border-subtle bg-transparent p-0 group-data-[orientation=horizontal]/tabs:h-8",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

const triggerBase =
  "relative inline-flex items-center justify-center gap-1.5 whitespace-nowrap transition-colors focus-visible:outline-1 focus-visible:outline-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0"

const triggerDefaultClass =
  "h-[calc(100%-1px)] flex-1 rounded-md border border-transparent px-2 py-1 text-sm font-medium text-foreground/60 transition-all group-data-[orientation=vertical]/tabs:w-full group-data-[orientation=vertical]/tabs:justify-start hover:text-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm dark:text-muted-foreground dark:hover:text-foreground dark:data-[state=active]:border-input dark:data-[state=active]:bg-input/30 dark:data-[state=active]:text-foreground [&_svg:not([class*='size-'])]:size-4"

const triggerLineClass =
  "h-full shrink-0 rounded-none px-3 text-sm text-muted-foreground hover:text-foreground focus-visible:text-foreground data-[state=active]:text-foreground after:absolute after:inset-x-0 after:bottom-[-1px] after:h-0.5 after:bg-primary after:opacity-0 after:transition-opacity data-[state=active]:after:opacity-100 [&_svg:not([class*='size-'])]:size-4"

function TabMarker() {
  return (
    <>
      <span aria-hidden className="size-1.5 rounded-pill bg-primary" />
      <span className="sr-only"> (non-default settings)</span>
    </>
  )
}

function TabCount({ count }: { count: number | string }) {
  return <span className="text-2xs text-subtle-foreground">{count}</span>
}

type TabsListProps = React.ComponentProps<typeof TabsPrimitive.List> &
  VariantProps<typeof tabsListVariants> & {
    /** Line variant only: hide tabs that do not fit behind a "more" menu. */
    overflow?: boolean
  }

const MORE_WIDTH = 36
const TAB_GAP = 4

function TabsList({ className, variant = "default", overflow, children, ...props }: TabsListProps) {
  const v: TabsVariant = variant ?? "default"
  const list = overflow && v === "line" ? (
    <OverflowList className={className} {...props}>{children}</OverflowList>
  ) : (
    <TabsPrimitive.List
      data-slot="tabs-list"
      data-variant={v}
      className={cn(tabsListVariants({ variant }), className)}
      {...props}
    >
      {children}
    </TabsPrimitive.List>
  )
  return <TabsVariantContext.Provider value={v}>{list}</TabsVariantContext.Provider>
}

type TriggerElement = React.ReactElement<TabsTriggerProps>

function sameNumbers(a: number[], b: number[]) {
  return a.length === b.length && a.every((n, i) => n === b[i])
}

function OverflowList({
  className,
  children,
  ...props
}: Omit<React.ComponentProps<typeof TabsPrimitive.List>, "variant">) {
  const { value, setValue } = React.useContext(TabsValueContext)
  const items = React.Children.toArray(children).filter(
    (c): c is TriggerElement => React.isValidElement(c) && typeof (c.props as { value?: unknown }).value === "string"
  )
  const wrapRef = React.useRef<HTMLDivElement>(null)
  const measureRef = React.useRef<HTMLDivElement>(null)
  const [widths, setWidths] = React.useState<number[]>([])
  const [available, setAvailable] = React.useState<number | null>(null)

  React.useLayoutEffect(() => {
    const wrap = wrapRef.current
    const measure = measureRef.current
    if (!wrap || !measure) return
    const update = () => {
      const w = Array.from(measure.children).map((el) => (el as HTMLElement).offsetWidth + TAB_GAP)
      setWidths((prev) => (sameNumbers(prev, w) ? prev : w))
      setAvailable(wrap.clientWidth)
    }
    update()
    const ro = new ResizeObserver(update)
    ro.observe(wrap)
    Array.from(measure.children).forEach((el) => ro.observe(el))
    return () => ro.disconnect()
  }, [items.length])

  const activeIndex = items.findIndex((c) => c.props.value === value)
  const { visible, hidden } =
    available === null || widths.length !== items.length
      ? { visible: items.map((_, i) => i), hidden: [] as number[] }
      : computeVisibleTabs(widths, available, MORE_WIDTH + TAB_GAP, activeIndex)

  return (
    <div ref={wrapRef} className="relative w-full min-w-0">
      <div
        ref={measureRef}
        aria-hidden
        className="pointer-events-none invisible absolute top-0 left-0 flex h-0 overflow-hidden"
      >
        {items.map((c) => (
          <span key={c.props.value} className={cn(triggerBase, triggerLineClass, "font-normal")}>
            <TabLabel {...c.props} />
          </span>
        ))}
      </div>
      <TabsPrimitive.List
        data-slot="tabs-list"
        data-variant="line"
        className={cn(tabsListVariants({ variant: "line" }), className)}
        {...props}
      >
        {visible.map((i) => items[i])}
        {hidden.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label="More tabs"
                className="ml-auto inline-flex h-full w-9 shrink-0 items-center justify-center text-muted-foreground outline-none hover:text-foreground focus-visible:text-foreground"
              >
                <Ellipsis className="size-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {hidden.map((i) => {
                const p = items[i].props
                return (
                  <DropdownMenuItem key={p.value} disabled={p.disabled} onSelect={() => setValue(p.value)}>
                    <TabLabel {...p} />
                  </DropdownMenuItem>
                )
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </TabsPrimitive.List>
    </div>
  )
}

type TabsTriggerProps = React.ComponentProps<typeof TabsPrimitive.Trigger> & {
  /** Small amber dot: this tab has non-default settings. */
  marker?: boolean
  count?: number | string
}

function TabLabel({ children, marker, count }: Pick<TabsTriggerProps, "children" | "marker" | "count">) {
  return (
    <>
      {children}
      {count !== undefined && <TabCount count={count} />}
      {marker && <TabMarker />}
    </>
  )
}

function TabsTrigger({ className, marker, count, children, ...props }: TabsTriggerProps) {
  const variant = React.useContext(TabsVariantContext)
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(triggerBase, variant === "line" ? triggerLineClass : triggerDefaultClass, className)}
      {...props}
    >
      <TabLabel marker={marker} count={count}>{children}</TabLabel>
    </TabsPrimitive.Trigger>
  )
}

function TabsContent({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn("flex-1 outline-none", className)}
      {...props}
    />
  )
}

export { Tabs, TabsList, TabsTrigger, TabsContent, tabsListVariants }
