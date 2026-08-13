import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { ReservationStatusBadge } from "@/components/reservation-status-badge"
import type { ReservationStatus } from "@/types/reservation"

describe("ReservationStatusBadge", () => {
  it.each<[ReservationStatus, string]>([
    ["requested", "Requested"],
    ["confirmed", "Confirmed"],
    ["seated", "Seated"],
    ["completed", "Completed"],
    ["no_show", "No-show"],
    ["canceled", "Canceled"],
  ])("labels %s as %s", (status, label) => {
    render(<ReservationStatusBadge status={status} />)
    expect(screen.getByText(label)).toBeInTheDocument()
  })
})
