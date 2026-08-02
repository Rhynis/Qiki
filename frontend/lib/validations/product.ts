import { z } from 'zod'

const sizeValues = ['6', '12', '45'] as const
const skuRegex = /^[A-Z0-9-]+$/
const categoryValues = ['gas', 'nuoc_uong'] as const
const unitValues = ['kg', 'lít'] as const
const optionalUrl = z
  .string()
  .trim()
  .url('URL hình ảnh không hợp lệ')
  .or(z.literal(''))
  .optional()
  .transform((value) => (value ? value : undefined))

const productBaseSchema = z.object({
  sku: z
    .string()
    .trim()
    .min(1, 'SKU không được để trống')
    .max(50, 'SKU quá dài')
    .transform((value) => value.toUpperCase())
    .refine((value) => skuRegex.test(value), 'SKU chỉ gồm chữ in hoa, số và dấu gạch ngang'),
  name: z.string().trim().min(1, 'Tên sản phẩm không được để trống').max(255, 'Tên quá dài'),
  brand: z.string().trim().min(1, 'Thương hiệu không được để trống').max(100, 'Tên quá dài'),
  category: z.enum(categoryValues).default('gas'),
  unit: z.enum(unitValues).default('kg'),
  size_kg: z
    .string()
    .trim()
    .min(1, 'Kích thước không được để trống')
    .regex(/^\d+(\.\d+)?$/, 'Kích thước phải là số'),
  price: z.string().trim().min(1, 'Giá không được để trống').regex(/^\d+$/, 'Giá phải là số'),
  sale_price: z
    .string()
    .trim()
    .regex(/^\d+$/, 'Giá khuyến mãi phải là số')
    .optional()
    .or(z.literal('')),
  stock_quantity: z.coerce.number().int('Tồn kho phải là số nguyên').min(0, 'Tồn kho không âm'),
  description: z.string().trim().optional(),
  long_description: z.string().trim().optional(),
  image_url: optionalUrl,
  safety_info: z.string().trim().optional(),
  pricing_note: z.string().trim().optional(),
  colour: z.string().trim().max(50, 'Màu quá dài').optional(),
  variant_label: z.string().trim().max(100, 'Nhãn quá dài').optional(),
})

function validateGasSize(value: { category?: string; size_kg?: string }, context: z.RefinementCtx) {
  if (
    value.category === 'gas' &&
    !sizeValues.includes(value.size_kg as (typeof sizeValues)[number])
  ) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Chọn kích thước bình gas',
      path: ['size_kg'],
    })
  }
}

function validateSalePrice(
  value: { price?: string; sale_price?: string },
  context: z.RefinementCtx
) {
  if (!value.sale_price) return
  const sale = Number(value.sale_price)
  const price = Number(value.price)
  if (!(sale > 0) || (value.price && sale >= price)) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Giá khuyến mãi phải lớn hơn 0 và nhỏ hơn giá gốc',
      path: ['sale_price'],
    })
  }
}

export const productSchema = productBaseSchema.superRefine((value, context) => {
  validateGasSize(value, context)
  validateSalePrice(value, context)
})

export const productUpdateSchema = productBaseSchema
  .partial()
  .extend({
    is_active: z.boolean().optional(),
  })
  .superRefine((value, context) => {
    validateGasSize(value, context)
    validateSalePrice(value, context)
  })

export const productFiltersSchema = z
  .object({
    search: z.string().trim().optional(),
    brand: z.string().trim().optional(),
    category: z.enum(categoryValues).optional(),
    min_price: z.string().trim().optional(),
    max_price: z.string().trim().optional(),
    size_kg: z.enum(sizeValues).optional(),
    in_stock_only: z.boolean().optional(),
    sort_by: z.enum(['created_at', 'price', 'name']).default('created_at'),
    sort_order: z.enum(['asc', 'desc']).default('desc'),
  })
  .refine(
    (value) =>
      !value.min_price ||
      !value.max_price ||
      Number.parseInt(value.min_price, 10) <= Number.parseInt(value.max_price, 10),
    { message: 'Giá tối thiểu phải nhỏ hơn giá tối đa', path: ['max_price'] }
  )

export type ProductFormValues = z.infer<typeof productSchema>
export type ProductUpdateValues = z.infer<typeof productUpdateSchema>
export type ProductFiltersValues = z.infer<typeof productFiltersSchema>
