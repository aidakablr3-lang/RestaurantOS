import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { OperatingHoursDialog } from "./page"

const replaceHoursMutateAsync = vi.fn()
vi.mock("@/hooks/use-branches", () => ({
  useReplaceOperatingHours: () => ({ mutateAsync: replaceHoursMutateAsync, isPending: false }),
}))

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

// Day order in the dialog is always Sunday(0) .. Saturday(6), matching
// buildWeek()'s Array.from({ length: 7 }, (_, dayOfWeek) => ...).
const SUNDAY = 0
const MONDAY = 1
const TUESDAY = 2
const WEDNESDAY = 3
const THURSDAY = 4

function renderDialog() {
  render(<OperatingHoursDialog branchId="b1" entries={[]} />)
  fireEvent.click(screen.getByRole("button", { name: "Edit hours" }))
}

function dayCheckboxes(): HTMLElement[] {
  return screen.getAllByRole("checkbox")
}

// Every day renders exactly [opensAt, closesAt] inputs in day order, so
// day N's opens/closes inputs are at indices [2N, 2N + 1].
function opensAtInput(dayOfWeek: number): HTMLInputElement {
  return (document.querySelectorAll('input[type="time"]')[dayOfWeek * 2] as HTMLInputElement)
}

function closesAtInput(dayOfWeek: number): HTMLInputElement {
  return (document.querySelectorAll('input[type="time"]')[dayOfWeek * 2 + 1] as HTMLInputElement)
}

function openDay(dayOfWeek: number) {
  fireEvent.click(dayCheckboxes()[dayOfWeek])
}

function setTimes(dayOfWeek: number, opensAt: string, closesAt: string) {
  fireEvent.change(opensAtInput(dayOfWeek), { target: { value: opensAt } })
  fireEvent.change(closesAtInput(dayOfWeek), { target: { value: closesAt } })
}

describe("OperatingHoursDialog — default-to-Monday and per-day override", () => {
  it("propagates Monday's hours to every other open day, leaving closed days alone", () => {
    renderDialog()

    openDay(MONDAY)
    openDay(TUESDAY)
    openDay(WEDNESDAY)
    // Thursday stays closed.
    setTimes(MONDAY, "09:00", "17:00")

    expect(opensAtInput(TUESDAY).value).toBe("09:00")
    expect(closesAtInput(TUESDAY).value).toBe("17:00")
    expect(opensAtInput(WEDNESDAY).value).toBe("09:00")
    expect(closesAtInput(WEDNESDAY).value).toBe("17:00")
    expect(opensAtInput(THURSDAY).disabled).toBe(true)
    expect(opensAtInput(THURSDAY).value).toBe("")
  })

  it("inherits Monday's current hours when a day is opened afterward (order independence)", () => {
    renderDialog()

    openDay(MONDAY)
    setTimes(MONDAY, "09:00", "17:00")
    // Thursday is opened only *after* Monday already has hours.
    openDay(THURSDAY)

    expect(opensAtInput(THURSDAY).value).toBe("09:00")
    expect(closesAtInput(THURSDAY).value).toBe("17:00")
  })

  it("stops a day from following Monday once it's edited directly, and 'Apply to all days' re-syncs it", () => {
    renderDialog()

    openDay(MONDAY)
    openDay(TUESDAY)
    setTimes(MONDAY, "09:00", "17:00")
    expect(opensAtInput(TUESDAY).value).toBe("09:00")

    // Direct edit on Tuesday is a per-day override.
    fireEvent.change(opensAtInput(TUESDAY), { target: { value: "10:00" } })
    // A later Monday edit must not clobber Tuesday's override.
    setTimes(MONDAY, "08:00", "18:00")
    expect(opensAtInput(TUESDAY).value).toBe("10:00")

    // "Apply to all days" explicitly re-syncs every open day to Monday.
    fireEvent.click(screen.getByRole("button", { name: "Apply to all days" }))
    expect(opensAtInput(TUESDAY).value).toBe("08:00")
    expect(closesAtInput(TUESDAY).value).toBe("18:00")

    // The override is cleared, so Monday keeps propagating afterward.
    setTimes(MONDAY, "07:00", "19:00")
    expect(opensAtInput(TUESDAY).value).toBe("07:00")
  })

  it("never touches a closed day's hours, even via 'Apply to all days'", () => {
    renderDialog()

    openDay(MONDAY)
    setTimes(MONDAY, "09:00", "17:00")
    // Sunday stays closed throughout.
    fireEvent.click(screen.getByRole("button", { name: "Apply to all days" }))

    expect(opensAtInput(SUNDAY).disabled).toBe(true)
    expect(opensAtInput(SUNDAY).value).toBe("")
  })
})
