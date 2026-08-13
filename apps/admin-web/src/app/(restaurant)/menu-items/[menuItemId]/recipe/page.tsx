"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useFieldArray, useForm } from "react-hook-form"
import { PlusIcon, TrashIcon } from "lucide-react"
import { toast } from "sonner"

import { PermissionRestricted } from "@/components/permission-restricted"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/ui/page-header"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useBranches } from "@/hooks/use-branches"
import { useInventoryItems } from "@/hooks/use-inventory"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { useMenuItemRecipe, useReviseRecipe } from "@/hooks/use-recipes"
import { ApiError } from "@/lib/api-client"
import { type ReviseRecipeFormValues, reviseRecipeSchema } from "@/lib/schemas/recipe"

export default function MenuItemRecipePage() {
  const params = useParams<{ menuItemId: string }>()
  const menuItemId = params.menuItemId

  const perms = usePermissionHelpers()
  const canRead = perms.hasTenantWide("menu.read")
  const canManage = perms.hasTenantWide("menu.manage")
  const enabled = !perms.isLoading && canRead

  const recipeQuery = useMenuItemRecipe(menuItemId, { enabled })
  const recipe = recipeQuery.data?.data
  const hasRecipe = Boolean(recipe) && !recipeQuery.isError

  // RecipeIngredient.inventoryItemId points at one specific, branch-scoped
  // InventoryItem row even though Recipe itself is tenant-wide (a
  // disclosed modeling tension inherited from the backend, not resolved
  // here -- see ReviseRecipeUseCase's own docstring). There is no
  // tenant-wide "list every inventory item" endpoint, so this page has
  // the operator pick one branch purely to source the ingredient
  // picklist from.
  const branchesQuery = useBranches({ offset: 0, limit: 100 }, { enabled })
  const branches = branchesQuery.data?.data ?? []
  const [pickerBranchId, setPickerBranchId] = React.useState<string>("")
  React.useEffect(() => {
    const firstBranchId = branchesQuery.data?.data[0]?.id
    if (!pickerBranchId && firstBranchId) setPickerBranchId(firstBranchId)
  }, [branchesQuery.data, pickerBranchId])
  const inventoryItemsQuery = useInventoryItems(
    pickerBranchId,
    { offset: 0, limit: 100 },
    { enabled: enabled && Boolean(pickerBranchId) }
  )
  const inventoryItems = inventoryItemsQuery.data?.data ?? []
  const inventoryItemNameById = new Map(inventoryItems.map((item) => [item.id, `${item.name} (${item.unit})`]))
  const inventoryItemLabels = Object.fromEntries(inventoryItems.map((item) => [item.id, `${item.name} (${item.unit})`]))
  const branchLabels = Object.fromEntries(branches.map((branch) => [branch.id, branch.name]))

  const reviseRecipe = useReviseRecipe(menuItemId)

  const form = useForm<ReviseRecipeFormValues>({
    resolver: zodResolver(reviseRecipeSchema),
    defaultValues: { name: "", ingredients: [] },
  })
  const fieldArray = useFieldArray({ control: form.control, name: "ingredients" })

  function startFromCurrent() {
    form.reset({
      name: recipe ? `${recipe.name} (revised)` : "",
      ingredients: (recipe?.ingredients ?? []).map((i) => ({
        inventoryItemId: i.inventoryItemId,
        quantity: Number(i.quantity),
        unit: i.unit,
      })),
    })
  }

  async function onSubmit(values: ReviseRecipeFormValues) {
    try {
      await reviseRecipe.mutateAsync({
        name: values.name,
        ingredients: values.ingredients.map((i) => ({
          inventoryItemId: i.inventoryItemId,
          quantity: String(i.quantity),
          unit: i.unit,
        })),
      })
      toast.success("Recipe saved.")
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to save this recipe.")
    }
  }

  const loading = perms.isLoading || recipeQuery.isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Recipe"
        description="Recipes are versioned -- saving always creates a new version and repoints this menu item at it."
      />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="this recipe" />
      ) : loading ? (
        <div className="grid gap-2">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-10 w-full" />
          ))}
        </div>
      ) : (
        <>
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Current recipe</CardTitle>
              {hasRecipe && recipe ? <Badge variant="secondary">v{recipe.version}</Badge> : null}
            </CardHeader>
            <CardContent>
              {!hasRecipe ? (
                <p className="text-sm text-muted-foreground">No recipe set for this menu item yet.</p>
              ) : (
                <div className="grid gap-3">
                  <p className="font-medium">{recipe?.name}</p>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Ingredient</TableHead>
                        <TableHead>Quantity</TableHead>
                        <TableHead>Unit</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {recipe?.ingredients.map((ingredient) => (
                        <TableRow key={ingredient.id}>
                          <TableCell className="font-medium">
                            {inventoryItemNameById.get(ingredient.inventoryItemId) ?? ingredient.inventoryItemId}
                          </TableCell>
                          <TableCell className="text-muted-foreground">{ingredient.quantity}</TableCell>
                          <TableCell className="text-muted-foreground">{ingredient.unit}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>

          {canManage ? (
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>Revise recipe</CardTitle>
                {hasRecipe ? (
                  <Button size="sm" variant="outline" onClick={startFromCurrent}>
                    Start from current version
                  </Button>
                ) : null}
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="grid max-w-xs gap-1.5">
                  <label className="text-sm font-medium">Ingredient picker branch</label>
                  <Select
                    value={pickerBranchId}
                    onValueChange={(value) => setPickerBranchId(value ?? "")}
                    items={branchLabels}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Choose a branch" />
                    </SelectTrigger>
                    <SelectContent>
                      {branches.map((branch) => (
                        <SelectItem key={branch.id} value={branch.id}>
                          {branch.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <Form {...form}>
                  <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
                    <FormField
                      control={form.control}
                      name="name"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Recipe name</FormLabel>
                          <FormControl>
                            <Input {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <div className="grid gap-3">
                      {fieldArray.fields.map((field, index) => (
                        <div key={field.id} className="grid grid-cols-[1fr_auto_auto_auto] items-end gap-2">
                          <FormField
                            control={form.control}
                            name={`ingredients.${index}.inventoryItemId`}
                            render={({ field: itemField }) => (
                              <FormItem>
                                {index === 0 ? <FormLabel>Inventory item</FormLabel> : null}
                                <Select
                                  value={itemField.value}
                                  onValueChange={itemField.onChange}
                                  items={inventoryItemLabels}
                                >
                                  <FormControl>
                                    <SelectTrigger className="w-full">
                                      <SelectValue placeholder="Choose an item" />
                                    </SelectTrigger>
                                  </FormControl>
                                  <SelectContent>
                                    {inventoryItems.map((item) => (
                                      <SelectItem key={item.id} value={item.id}>
                                        {item.name}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name={`ingredients.${index}.quantity`}
                            render={({ field: qtyField }) => (
                              <FormItem>
                                {index === 0 ? <FormLabel>Quantity</FormLabel> : null}
                                <FormControl>
                                  <Input type="number" min={0} step="0.01" className="w-24" {...qtyField} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name={`ingredients.${index}.unit`}
                            render={({ field: unitField }) => (
                              <FormItem>
                                {index === 0 ? <FormLabel>Unit</FormLabel> : null}
                                <FormControl>
                                  <Input className="w-20" {...unitField} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            aria-label="Remove ingredient"
                            onClick={() => fieldArray.remove(index)}
                          >
                            <TrashIcon />
                          </Button>
                        </div>
                      ))}
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="w-fit"
                        onClick={() => fieldArray.append({ inventoryItemId: "", quantity: 1, unit: "" })}
                      >
                        <PlusIcon />
                        Add ingredient
                      </Button>
                    </div>

                    <Button type="submit" disabled={reviseRecipe.isPending} className="w-fit">
                      {reviseRecipe.isPending ? "Saving…" : "Save new version"}
                    </Button>
                  </form>
                </Form>
              </CardContent>
            </Card>
          ) : null}
        </>
      )}
    </div>
  )
}
