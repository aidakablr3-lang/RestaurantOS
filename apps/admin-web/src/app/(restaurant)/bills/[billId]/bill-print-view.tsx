"use client"

/**
 * 80mm thermal-receipt print view for a bill. Rendered off-screen at
 * all times (`hidden print:block`) -- window.print() on the bill
 * detail page shows only this subtree, per globals.css's @page rule.
 *
 * Composed entirely from existing endpoints (bill, order, branch,
 * restaurant, tables, taxes, payments) -- no dedicated backend
 * endpoint for this exists or was added; every field here is already
 * fetchable, just not previously joined together in one view.
 *
 * "Bill ID" is the raw Bill.id (a ULID), deliberately not labeled
 * "Invoice No." -- it is not a consecutive, financial-year-scoped
 * series, which a compliant GST tax invoice number must be. See the
 * accompanying gap report; this print view does not claim to be a
 * legally complete tax invoice on its own yet.
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
  const total = (subtotal + tax + adjustments).toFixed(2)

  const addressLine = branch?.address
    ? [branch.address.line1, branch.address.city, branch.address.postalCode]
        .filter(Boolean)
        .join(", ")
    : null

  return (
    <div className="hidden print:block w-[76mm] text-xs leading-snug">
      <div className="text-center">
        <p className="text-sm font-bold">{restaurant?.legalName ?? restaurant?.displayName}</p>
        {addressLine ? <p>{addressLine}</p> : null}
        {branch?.gstin ? <p>GSTIN: {branch.gstin}</p> : null}
      </div>

      <div className="my-1 border-t border-dashed border-black" />

      <p>Bill ID: {bill.id}</p>
      <p>Date: {new Date(bill.createdAt).toLocaleString()}</p>
      {tableNumber ? <p>Table: {tableNumber}</p> : null}

      <div className="my-1 border-t border-dashed border-black" />

      <table className="w-full">
        <thead>
          <tr className="border-b border-dashed border-black text-left">
            <th className="font-normal">Item</th>
            <th className="w-6 text-right font-normal">Qty</th>
            <th className="w-10 text-right font-normal">Rate</th>
            <th className="w-12 text-right font-normal">Amount</th>
          </tr>
        </thead>
        <tbody>
          {(order?.items ?? []).map((item) => (
            <tr key={item.id}>
              <td>{menuItemNameById.get(item.menuItemId) ?? item.menuItemId}</td>
              <td className="text-right">{item.quantity}</td>
              <td className="text-right">{item.unitPriceAmount}</td>
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
        <span>{subtotal.toFixed(2)}</span>
      </div>
      {bill.taxLines.map((line) => (
        <div key={line.id} className="flex justify-between">
          <span>
            {taxNameById.get(line.taxId) ?? "Tax"} @{" "}
            {(Number(line.taxRateSnapshot) * 100).toFixed(2)}%
          </span>
          <span>{line.taxAmount}</span>
        </div>
      ))}
      <div className="my-1 border-t border-dashed border-black" />
      <div className="flex justify-between text-sm font-bold">
        <span>Total</span>
        <span>{total}</span>
      </div>

      <div className="my-1 border-t border-dashed border-black" />

      <p>
        Payment:{" "}
        {payments.length === 0
          ? "Pending"
          : payments
              .map((p) => `${TENDER_TYPE_LABEL[p.tenderType] ?? p.tenderType} ${p.amount}`)
              .join(", ")}
      </p>
    </div>
  )
}
