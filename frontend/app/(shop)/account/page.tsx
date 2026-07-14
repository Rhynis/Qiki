'use client'

import {
  BadgeCheck,
  ClipboardList,
  Heart,
  KeyRound,
  Mail,
  MapPin,
  Phone,
  ShieldAlert,
  ShieldCheck,
  UserRound,
} from 'lucide-react'
import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { EmailOtpVerification } from '@/components/auth/email-otp-verification'
import { PageHeader } from '@/components/shared/page-header'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/lib/hooks/use-auth'
import { formatPhone } from '@/lib/utils/format'
import { deliveryWardGroups } from '@/utils/vietnamese-address'

const DEFAULT_CITY = 'TP. Hồ Chí Minh'

export default function AccountPage() {
  const t = useTranslations('account')
  const tCommon = useTranslations('common')
  const router = useRouter()
  const { user, isLoading, refreshUser, updateProfile } = useAuth()
  const roleLabels: Record<string, string> = {
    admin: t('roleAdmin'),
    staff: t('roleStaff'),
    customer: t('roleCustomer'),
  }
  const displayValue = (value: string | null | undefined) =>
    value?.trim() ? value : t('notUpdated')
  const [checked, setChecked] = useState(false)
  const [delivery, setDelivery] = useState({
    address: '',
    delivery_ward: '',
    delivery_city: DEFAULT_CITY,
    delivery_notes: '',
  })
  const [syncedUserId, setSyncedUserId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let mounted = true
    refreshUser()
      .then((currentUser) => {
        if (!currentUser) {
          router.replace('/login?redirectTo=/account')
        }
      })
      .finally(() => {
        if (mounted) setChecked(true)
      })
    return () => {
      mounted = false
    }
  }, [refreshUser, router])

  // Seed the editable form from the account the first time this user loads (and
  // on account switch). Adjusting state during render — not in an effect — avoids
  // a cascading-render cycle and never clobbers an in-progress edit.
  if (user && user.id !== syncedUserId) {
    setSyncedUserId(user.id)
    setDelivery({
      address: user.address ?? '',
      delivery_ward: user.delivery_ward ?? '',
      delivery_city: user.delivery_city ?? DEFAULT_CITY,
      delivery_notes: user.delivery_notes ?? '',
    })
  }

  if (!checked || isLoading) {
    return (
      <section className="mx-auto max-w-4xl px-4 py-8">
        <div className="rounded-lg border bg-white p-6 text-sm text-slate-600">
          {tCommon('loading')}
        </div>
      </section>
    )
  }

  if (!user) return null

  const emailVerified = Boolean(user.email) && user.email_verified

  const details: Array<{
    label: string
    value: string
    icon: typeof UserRound
    trailing?: ReactNode
  }> = [
    { label: t('fullName'), value: displayValue(user.full_name), icon: UserRound },
    {
      label: t('email'),
      value: displayValue(user.email),
      icon: Mail,
      trailing: emailVerified ? (
        <span className="inline-flex items-center text-emerald-600" title={t('emailVerified')}>
          <BadgeCheck className="h-4 w-4 shrink-0" aria-label={t('emailVerified')} />
        </span>
      ) : null,
    },
    {
      label: t('phone'),
      value: user.phone ? formatPhone(user.phone) : t('notUpdated'),
      icon: Phone,
    },
    { label: t('role'), value: roleLabels[user.role] ?? user.role, icon: ShieldCheck },
  ]

  const saveDelivery = async () => {
    setSaving(true)
    try {
      await updateProfile({
        address: delivery.address,
        delivery_ward: delivery.delivery_ward,
        // Never persist an empty city over the default.
        delivery_city: delivery.delivery_city.trim() || DEFAULT_CITY,
        delivery_notes: delivery.delivery_notes,
      })
      toast.success(t('savedDelivery'))
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : t('saveError'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="mx-auto max-w-4xl space-y-6 px-4 py-8">
      <PageHeader title={t('title')} description={t('description')} />

      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <div className="grid gap-4 sm:grid-cols-2">
          {details.map((item) => {
            const Icon = item.icon
            return (
              <div key={item.label} className="rounded-lg border bg-slate-50 p-4">
                <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-600">
                  <Icon className="h-4 w-4 text-primary" />
                  {item.label}
                </div>
                <p className="flex items-center gap-1.5 break-words text-base font-semibold text-slate-950">
                  <span className="break-words">{item.value}</span>
                  {item.trailing}
                </p>
              </div>
            )
          })}
        </div>

        {/* Prompt to verify only when an email exists but is not yet verified. */}
        {user.email && !user.email_verified ? (
          <div className="mt-6 rounded-lg border bg-amber-50 p-4">
            <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-amber-700">
              <ShieldAlert className="h-4 w-4" />
              {t('emailUnverified')}
            </div>
            <div className="mt-3">
              <EmailOtpVerification email={user.email} onVerified={() => void refreshUser()} />
            </div>
          </div>
        ) : null}

        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <Button asChild>
            <Link href="/forgot-password">
              <KeyRound className="mr-2 h-4 w-4" />
              {t('changePassword')}
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/orders">
              <ClipboardList className="mr-2 h-4 w-4" />
              {t('myOrders')}
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/wishlist">
              <Heart className="mr-2 h-4 w-4" />
              {t('wishlist')}
            </Link>
          </Button>
        </div>
      </div>

      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center gap-2">
          <MapPin className="h-5 w-5 text-primary" />
          <div>
            <h2 className="text-base font-semibold text-slate-950">{t('defaultAddressTitle')}</h2>
            <p className="text-sm text-slate-600">{t('defaultAddressSubtitle')}</p>
          </div>
        </div>

        <div className="grid gap-4">
          <div className="space-y-2">
            <Label htmlFor="account_address">{t('address')}</Label>
            <Input
              id="account_address"
              value={delivery.address}
              placeholder={t('addressPlaceholder')}
              onChange={(event) =>
                setDelivery((prev) => ({ ...prev, address: event.target.value }))
              }
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="account_ward">{t('ward')}</Label>
              {/* Same ward list as checkout so a saved ward prefills the checkout
                  <select> cleanly (a free-text ward would not match its options). */}
              <select
                id="account_ward"
                aria-label={t('ward')}
                className="h-10 w-full rounded-md border bg-white px-3 text-sm"
                value={delivery.delivery_ward}
                onChange={(event) =>
                  setDelivery((prev) => ({ ...prev, delivery_ward: event.target.value }))
                }
              >
                <option value="">{t('selectWard')}</option>
                {deliveryWardGroups.map((group) => (
                  <optgroup key={group.name} label={group.name}>
                    {group.wards.map((ward) => (
                      <option key={ward.name} value={ward.name}>
                        {ward.name}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="account_city">{t('city')}</Label>
              <Input
                id="account_city"
                value={delivery.delivery_city}
                onChange={(event) =>
                  setDelivery((prev) => ({ ...prev, delivery_city: event.target.value }))
                }
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="account_notes">{t('deliveryNotes')}</Label>
            <Textarea
              id="account_notes"
              value={delivery.delivery_notes}
              placeholder={t('deliveryNotesPlaceholder')}
              onChange={(event) =>
                setDelivery((prev) => ({ ...prev, delivery_notes: event.target.value }))
              }
            />
          </div>
          <div>
            <Button type="button" disabled={saving} onClick={saveDelivery}>
              {saving ? t('saving') : t('saveDelivery')}
            </Button>
          </div>
        </div>
      </div>
    </section>
  )
}
