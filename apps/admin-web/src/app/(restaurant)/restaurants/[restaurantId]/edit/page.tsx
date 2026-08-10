"use client"

import * as React from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useRestaurant, useUpdateRestaurant } from "@/hooks/use-restaurants"
import { ApiError } from "@/lib/api-client"
import { type RestaurantFormValues, restaurantSchema } from "@/lib/schemas/restaurant"

export default function EditRestaurantPage() {
  const params = useParams<{ restaurantId: string }>()
  const router = useRouter()
  const restaurantId = params.restaurantId

  const { data, isLoading } = useRestaurant(restaurantId)
  const restaurant = data?.data
  const updateRestaurant = useUpdateRestaurant(restaurantId)

  const form = useForm<RestaurantFormValues>({
    resolver: zodResolver(restaurantSchema),
    defaultValues: { legalName: "", displayName: "", defaultCurrencyCode: "" },
  })

  React.useEffect(() => {
    if (restaurant) {
      form.reset({
        legalName: restaurant.legalName,
        displayName: restaurant.displayName,
        defaultCurrencyCode: restaurant.defaultCurrencyCode,
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [restaurant])

  async function onSubmit(values: RestaurantFormValues) {
    try {
      await updateRestaurant.mutateAsync(values)
      toast.success("Restaurant updated.")
      router.push(`/restaurants/${restaurantId}`)
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "Failed to update restaurant."
      )
    }
  }

  if (isLoading) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full max-w-lg" />
      </div>
    )
  }

  return (
    <div className="grid gap-6">
      <div>
        <p className="text-sm text-muted-foreground">
          <Link href="/restaurants" className="hover:underline">
            Restaurants
          </Link>{" "}
          /{" "}
          <Link href={`/restaurants/${restaurantId}`} className="hover:underline">
            {restaurant?.displayName ?? restaurantId}
          </Link>{" "}
          / Edit
        </p>
        <h1 className="text-xl font-semibold">Edit restaurant</h1>
      </div>

      <Card className="max-w-lg">
        <CardHeader>
          <CardTitle>Restaurant details</CardTitle>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(onSubmit)}
              className="grid gap-4"
              noValidate
            >
              <FormField
                control={form.control}
                name="legalName"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Legal name</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="displayName"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Display name</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="defaultCurrencyCode"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Default currency</FormLabel>
                    <FormControl>
                      <Input
                        maxLength={3}
                        {...field}
                        onChange={(event) =>
                          field.onChange(event.target.value.toUpperCase())
                        }
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="mt-2 flex gap-2">
                <Button type="submit" disabled={updateRestaurant.isPending}>
                  {updateRestaurant.isPending ? "Saving…" : "Save changes"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  render={<Link href={`/restaurants/${restaurantId}`} />}
                  nativeButton={false}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  )
}
