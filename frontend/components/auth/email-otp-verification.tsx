'use client'

import { useTranslations } from 'next-intl'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { requestEmailOtp, verifyEmailOtp } from '@/lib/api/auth'

const RESEND_COOLDOWN_SECONDS = 60

interface EmailOtpVerificationProps {
  email: string
  onVerified?: () => void
}

/** Sends an email-verification OTP on demand and verifies the submitted code. */
export function EmailOtpVerification({ email, onVerified }: EmailOtpVerificationProps) {
  const t = useTranslations('auth')
  const [sent, setSent] = useState(false)
  const [code, setCode] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [cooldown, setCooldown] = useState(0)

  useEffect(() => {
    if (cooldown <= 0) return
    const timer = setInterval(() => setCooldown((value) => Math.max(0, value - 1)), 1000)
    return () => clearInterval(timer)
  }, [cooldown])

  const sendOtp = async () => {
    setError(null)
    try {
      await requestEmailOtp(email)
      setSent(true)
      setCooldown(RESEND_COOLDOWN_SECONDS)
      toast.success(t('otpSent'))
    } catch {
      toast.error(t('otpSendFailed'))
    }
  }

  const verify = async () => {
    setError(null)
    setSubmitting(true)
    try {
      await verifyEmailOtp(email, code)
      toast.success(t('otpVerified'))
      onVerified?.()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t('otpInvalid'))
    } finally {
      setSubmitting(false)
    }
  }

  if (!sent) {
    return (
      <Button onClick={() => void sendOtp()} size="sm" type="button" variant="outline">
        {t('otpSendCode')}
      </Button>
    )
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">{t('otpEnterCode')}</p>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          aria-label={t('otpCodeLabel')}
          id="otp_code"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          value={code}
          onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
          className="h-10 w-full rounded-md border px-3 text-center text-lg tracking-[0.4em] outline-none focus:ring-2 focus:ring-ring sm:w-40"
        />
        <Button
          disabled={submitting || code.length !== 6}
          onClick={() => void verify()}
          type="button"
        >
          {submitting ? t('verifying') : t('verify')}
        </Button>
        <Button
          disabled={cooldown > 0}
          onClick={() => void sendOtp()}
          type="button"
          variant="outline"
        >
          {cooldown > 0 ? t('resendCodeCooldown', { seconds: cooldown }) : t('resendCode')}
        </Button>
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
    </div>
  )
}
