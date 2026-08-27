"use client"

import * as React from "react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { toast } from "sonner"

import { ApiError } from "@/lib/api-client"
import { activateOwner } from "@/lib/api/owner-activation"
import { type ActivateOwnerFormValues, activateOwnerSchema } from "@/lib/schemas/owner-activation"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"

function ActivateForm() {
  const token = useSearchParams().get("token")
  const [isSubmitting, setIsSubmitting] = React.useState(false)
  const [activated, setActivated] = React.useState(false)

  const form = useForm<ActivateOwnerFormValues>({
    resolver: zodResolver(activateOwnerSchema),
    defaultValues: { newPassword: "", confirmPassword: "" },
  })

  async function onSubmit(values: ActivateOwnerFormValues) {
    if (!token) return
    setIsSubmitting(true)
    try {
      await activateOwner({ token, newPassword: values.newPassword })
      setActivated(true)
    } catch (error) {
      // The API deliberately returns the same message for an unknown,
      // expired, or already-used token -- distinguishing them here
      // would leak which one it was to whoever holds the link.
      const message = error instanceof ApiError ? error.message : "Unable to activate this account."
      toast.error(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!token) {
    return (
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Activation link is incomplete</CardTitle>
          <CardDescription>
            This link is missing its activation token. Ask whoever created your account to resend
            it, or check that you copied the full link.
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (activated) {
    return (
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Account activated</CardTitle>
          <CardDescription>
            Your password is set. Sign in with your email and new password to continue.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button render={<Link href="/login" />} nativeButton={false} className="w-full">
            Go to sign in
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="w-full max-w-sm">
      <CardHeader>
        <CardTitle>Activate your account</CardTitle>
        <CardDescription>Set a password to finish setting up your RestaurantOS account.</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="newPassword"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>New password</FormLabel>
                  <FormControl>
                    <Input type="password" autoComplete="new-password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="confirmPassword"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Confirm password</FormLabel>
                  <FormControl>
                    <Input type="password" autoComplete="new-password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button type="submit" disabled={isSubmitting} className="mt-2">
              {isSubmitting ? "Activating…" : "Activate account"}
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}

export default function ActivatePage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <React.Suspense fallback={null}>
        <ActivateForm />
      </React.Suspense>
    </div>
  )
}
