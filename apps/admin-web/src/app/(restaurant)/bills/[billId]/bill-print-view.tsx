"use client"

/**
 * 80mm thermal-receipt print view for a bill. Rendered off-screen at
 * all times (`hidden print:block`) -- window.print() on the bill
 * detail page shows only this subtree, per globals.css's @page rule
 * and its `.print-receipt` visibility isolation (which hides the rest
 * of the admin shell -- sidebar, header, tenant id, dark-mode toggle,
 * account avatar -- none of which has its own print:hidden class, so
 * without that global rule every one of those prints too).
 *
 * Heading is conditional, not always "TAX INVOICE": that heading only
 * belongs on a document that actually carries a compliant GST invoice
 * number. A branch with no gstin on file gets a plain "RECEIPT"
 * instead, matching this file's own established rule below (never
 * claims a compliant invoice number exists when it doesn't) -- calling
 * an uncompliant printout a "tax invoice" would be actively wrong, not
 * just an omission.
 *
 * Composed entirely from existing endpoints (bill, order, branch,
 * restaurant, tables, taxes, payments) -- no dedicated backend
 * endpoint for this exists or was added; every field here is already
 * fetchable, just not previously joined together in one view.
 *
 * Shows "Invoice No." when the bill has a real invoiceNumber
 * (GenerateBillUseCase only allocates one when the branch had a gstin
 * on file at generation time), falling back to the raw Bill.id
 * labeled plainly as "Bill ID" otherwise -- never claims a compliant
 * invoice number exists when it doesn't.
 */

import { useBranch } from "@/hooks/use-branches"
import { useTaxes } from "@/hooks/use-bills"
import { useRestaurantMenuItems } from "@/hooks/use-menu-items"
import { useOrder } from "@/hooks/use-orders"
import { usePayments } from "@/hooks/use-payments"
import { useRestaurant } from "@/hooks/use-restaurants"
import { useTables } from "@/hooks/use-tables"
import type { Bill } from "@/types/bill"

const TENDER_TYPE_LABEL: Record<string, string> = {
  cash: "Cash",
  card: "Card",
  wallet: "Wallet",
}

function money(value: number | string): string {
  return `₹${Number(value).toFixed(2)}`
}

export function BillPrintView({ bill }: { bill: Bill }) {
  const branchQuery = useBranch(bill.branchId)
  const branch = branchQuery.data?.data

  const restaurantQuery = useRestaurant(branch?.restaurantId)
  const restaurant = restaurantQuery.data?.data

  const orderQuery = useOrder(bill.branchId, bill.orderId ?? undefined, {
    enabled: Boolean(bill.orderId),
  })
  const order = orderQuery.data?.data

  const menuItemsQuery = useRestaurantMenuItems(branch?.restaurantId ?? "", {
    enabled: Boolean(branch?.restaurantId),
  })
  const menuItemNameById = new Map(menuItemsQuery.data.map((item) => [item.id, item.name]))

  const tablesQuery = useTables(bill.branchId, { offset: 0, limit: 100 })
  const tableNumberById = new Map((tablesQuery.data?.data ?? []).map((t) => [t.id, t.tableNumber]))
  const tableNumber = order?.tableId ? (tableNumberById.get(order.tableId) ?? null) : null

  const taxesQuery = useTaxes()
  const taxNameById = new Map((taxesQuery.data?.data ?? []).map((t) => [t.id, t.name]))

  const paymentsQuery = usePayments(bill.id)
  const payments = paymentsQuery.data?.data ?? []

  const subtotal = Number(bill.subtotalAmount)
  const tax = Number(bill.taxAmount)
  const adjustments = Number(bill.adjustmentsTotal)
  const total = subtotal + tax + adjustments

  const addressLine = branch?.address
    ? [
        branch.address.line1,
        branch.address.city,
        branch.address.state,
        branch.address.postalCode,
      ]
        .filter(Boolean)
        .join(", ")
    : null

  return (
    <div className="print-receipt hidden print:block w-[72mm] text-xs leading-snug">
      <p className="text-center text-sm font-bold">
        {bill.invoiceNumber ? "TAX INVOICE" : "RECEIPT"}
      </p>

      <div className="text-center">
        <p className="text-sm font-bold">{restaurant?.legalName ?? restaurant?.displayName}</p>
        {addressLine ? <p>{addressLine}</p> : null}
        {branch?.gstin ? <p>GSTIN: {branch.gstin}</p> : null}
      </div>

      <div className="my-1 border-t border-dashed border-black" />

      <p>{bill.invoiceNumber ? `Invoice No: ${bill.invoiceNumber}` : `Bill ID: ${bill.id}`}</p>
      <p>Date: {new Date(bill.createdAt).toLocaleString()}</p>
      {tableNumber ? <p>Table: {tableNumber}</p> : null}

      <div className="my-1 border-t border-dashed border-black" />

      <table className="w-full table-fixed border-collapse">
        <colgroup>
          <col className="w-[46%]" />
          <col className="w-[12%]" />
          <col className="w-[20%]" />
          <col className="w-[22%]" />
        </colgroup>
        <thead>
          <tr className="border-b border-dashed border-black text-left">
            <th className="pr-1 font-normal">Item</th>
            <th className="pr-1 text-right font-normal">Qty</th>
            <th className="pr-1 text-right font-normal">Rate</th>
            <th className="text-right font-normal">Amount</th>
          </tr>
        </thead>
        <tbody>
          {(order?.items ?? []).map((item) => (
            <tr key={item.id}>
              <td className="pr-1 break-words">
                {menuItemNameById.get(item.menuItemId) ?? item.menuItemId}
              </td>
              <td className="pr-1 text-right">{item.quantity}</td>
              <td className="pr-1 text-right">{Number(item.unitPriceAmount).toFixed(2)}</td>
              <td className="text-right">
                {(Number(item.unitPriceAmount) * item.quantity).toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="my-1 border-t border-dashed border-black" />

      <div className="flex justify-between">
        <span>Subtotal</span>
        <span>{money(subtotal)}</span>
      </div>
      {bill.taxLines.map((line) => (
        <div key={line.id} className="flex justify-between">
          <span>
            {taxNameById.get(line.taxId) ?? "Tax"} @{" "}
            {(Number(line.taxRateSnapshot) * 100).toFixed(2)}%
          </span>
          <span>{money(line.taxAmount)}</span>
        </div>
      ))}
      <div className="my-1 border-t border-dashed border-black" />
      <div className="flex justify-between text-sm font-bold">
        <span>Total</span>
        <span>{money(total)}</span>
      </div>

      <div className="my-1 border-t border-dashed border-black" />

      <p>
        Payment:{" "}
        {payments.length === 0
          ? "Pending"
          : payments
              .map((p) => `${TENDER_TYPE_LABEL[p.tenderType] ?? p.tenderType} ${money(p.amount)}`)
              .join(", ")}
      </p>
    </div>
  )
}
