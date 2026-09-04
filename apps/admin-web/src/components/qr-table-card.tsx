import { QRCodeSVG } from "qrcode.react"

// Fixed physical size (not px) so this renders identically whether it's
// the lone card on qr-code-print-view.tsx or one cell in a grid on
// qr-code-sheet-print-view.tsx -- both share globals.css's "qr-print"
// named @page (A4), and a 90mm-square card is what tiles cleanly into
// that page's usable area at 2 columns x 3 rows with a 12mm margin.
export function QRTableCard({
  url,
  tableNumber,
  restaurantName,
}: {
  url: string
  tableNumber: string
  restaurantName: string
}) {
  return (
    <div className="qr-table-card flex h-[90mm] w-[90mm] flex-col items-center justify-center gap-3 border border-dashed border-neutral-400 p-4 text-center print:break-inside-avoid">
      <QRCodeSVG value={url} size={256} className="h-[45mm] w-[45mm]" />
      <div>
        <p className="text-[4mm] leading-tight font-bold">{restaurantName}</p>
        <p className="text-[3.5mm] leading-tight">Table {tableNumber}</p>
        <p className="text-[3mm] leading-tight text-neutral-600">Scan to order</p>
      </div>
    </div>
  )
}
