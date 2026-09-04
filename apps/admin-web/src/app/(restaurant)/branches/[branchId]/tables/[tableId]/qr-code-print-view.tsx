"use client"

/**
 * Print-only view for one table's QR card -- hidden on screen at all
 * times (`hidden print:flex`), shown by window.print() on the table
 * detail page. Same isolation approach as bill-print-view.tsx: a marker
 * class (`.print-qr-card`, see globals.css) is the only thing left
 * visible under `body * { visibility: hidden }`, and it carries its own
 * named `@page` (A4, not the receipt's 80mm roll) via `page: qr-print`.
 */

import { QRTableCard } from "@/components/qr-table-card"

export function QRCodePrintView({
  url,
  tableNumber,
  restaurantName,
}: {
  url: string
  tableNumber: string
  restaurantName: string
}) {
  return (
    <div className="print-qr-card hidden print:flex print:h-full print:w-full print:items-center print:justify-center">
      <QRTableCard url={url} tableNumber={tableNumber} restaurantName={restaurantName} />
    </div>
  )
}
