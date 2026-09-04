"use client"

/**
 * Print-only A4 sheet of every table's QR card for one branch -- same
 * isolation approach as bill-print-view.tsx / qr-code-print-view.tsx,
 * keyed off `.print-qr-sheet` (see globals.css) and the shared
 * `qr-print` named @page. Cards render in a 2-column grid with no gap;
 * each QRTableCard's own dashed border becomes the shared cut line
 * between adjacent cards, so no separate divider markup is needed.
 */

import { QRTableCard } from "@/components/qr-table-card"

export interface QRSheetCard {
  tableId: string
  tableNumber: string
  url: string
}

export function QRCodeSheetPrintView({
  cards,
  restaurantName,
}: {
  cards: QRSheetCard[]
  restaurantName: string
}) {
  return (
    <div className="print-qr-sheet hidden print:grid print:grid-cols-2 print:content-start print:gap-0">
      {cards.map((card) => (
        <QRTableCard
          key={card.tableId}
          url={card.url}
          tableNumber={card.tableNumber}
          restaurantName={restaurantName}
        />
      ))}
    </div>
  )
}
