import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground",
        secondary: "bg-secondary text-secondary-foreground",
        destructive: "bg-destructive text-destructive-foreground",
        outline: "border border-input bg-background text-foreground",
        amber: "bg-amber-100 text-amber-800",
        orange: "bg-orange-100 text-orange-700",
        blue: "bg-blue-100 text-blue-800",
        sky: "bg-sky-100 text-sky-700",
        violet: "bg-violet-100 text-violet-800",
        emerald: "bg-emerald-100 text-emerald-800",
        red: "bg-red-100 text-red-800",
        slate: "bg-slate-100 text-slate-800",
        indigo: "bg-indigo-100 text-indigo-800",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
