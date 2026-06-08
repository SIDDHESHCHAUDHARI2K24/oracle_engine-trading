import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useChangePassword } from '../api/useChangePassword'
import { useSessions } from '../api/useSessions'
import { useLogoutEverywhere } from '../api/useLogoutEverywhere'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '../../../shared/components/ui/card'
import type { SessionInfo } from '../../../core/types'

const changePasswordSchema = z
  .object({
    oldPassword: z.string().min(1, 'Current password is required'),
    newPassword: z.string().min(12, 'Password must be at least 12 characters'),
    confirmPassword: z.string(),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })

type ChangePasswordFormData = z.infer<typeof changePasswordSchema>

function formatRelative(dateStr: string): string {
  const date = new Date(dateStr)
  const now = Date.now()
  const diffMs = now - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) return 'Just now'
  if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`
  if (diffDays < 30) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`
  return date.toLocaleDateString()
}

function SessionRow({ session }: { readonly session: SessionInfo }): JSX.Element {
  const ua = (session.user_agent ?? '').slice(0, 50)

  return (
    <tr className="border-t">
      <td className="p-3 text-sm">{ua || '\u2014'}</td>
      <td className="p-3 text-sm">{session.ip ?? '\u2014'}</td>
      <td className="p-3 text-sm">
        {session.last_used_at ? formatRelative(session.last_used_at) : '\u2014'}
      </td>
      <td className="p-3 text-sm">
        {session.is_current ? (
          <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
            This device
          </span>
        ) : null}
      </td>
    </tr>
  )
}

export function AccountSettingsPage(): JSX.Element {
  const changePassword = useChangePassword()
  const sessions = useSessions()
  const logoutEverywhere = useLogoutEverywhere()
  const [passwordSuccess, setPasswordSuccess] = useState(false)

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ChangePasswordFormData>({
    resolver: zodResolver(changePasswordSchema),
  })

  const onSubmit = (data: ChangePasswordFormData): void => {
    changePassword.mutate(
      { old_password: data.oldPassword, new_password: data.newPassword },
      {
        onSuccess: () => {
          setPasswordSuccess(true)
          reset()
          setTimeout(() => setPasswordSuccess(false), 5000)
        },
      },
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8 p-6">
      <h1 className="text-3xl font-bold">Account Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle>Change Password</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={handleSubmit(onSubmit)}
            className="max-w-md space-y-4"
            noValidate
          >
            <div className="space-y-1">
              <label
                htmlFor="oldPassword"
                className="text-sm font-medium"
              >
                Current Password
              </label>
              <Input
                id="oldPassword"
                type="password"
                autoComplete="current-password"
                aria-describedby={
                  errors.oldPassword ? 'oldPassword-error' : undefined
                }
                {...register('oldPassword')}
              />
              {errors.oldPassword && (
                <p
                  id="oldPassword-error"
                  className="text-sm text-red-600"
                  role="alert"
                >
                  {errors.oldPassword.message}
                </p>
              )}
            </div>
            <div className="space-y-1">
              <label
                htmlFor="newPassword"
                className="text-sm font-medium"
              >
                New Password
              </label>
              <Input
                id="newPassword"
                type="password"
                autoComplete="new-password"
                aria-describedby={
                  errors.newPassword ? 'newPassword-error' : undefined
                }
                {...register('newPassword')}
              />
              {errors.newPassword && (
                <p
                  id="newPassword-error"
                  className="text-sm text-red-600"
                  role="alert"
                >
                  {errors.newPassword.message}
                </p>
              )}
            </div>
            <div className="space-y-1">
              <label
                htmlFor="confirmPassword"
                className="text-sm font-medium"
              >
                Confirm New Password
              </label>
              <Input
                id="confirmPassword"
                type="password"
                autoComplete="new-password"
                aria-describedby={
                  errors.confirmPassword
                    ? 'confirmPassword-error'
                    : undefined
                }
                {...register('confirmPassword')}
              />
              {errors.confirmPassword && (
                <p
                  id="confirmPassword-error"
                  className="text-sm text-red-600"
                  role="alert"
                >
                  {errors.confirmPassword.message}
                </p>
              )}
            </div>
            {changePassword.isError && (
              <p className="text-sm text-red-600" role="alert">
                {changePassword.error.message}
              </p>
            )}
            {passwordSuccess && (
              <p className="text-sm text-green-600" role="status">
                Password changed successfully.
              </p>
            )}
            <Button type="submit" disabled={changePassword.isPending}>
              {changePassword.isPending
                ? 'Changing\u2026'
                : 'Change Password'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Active Sessions</CardTitle>
        </CardHeader>
        <CardContent>
          {sessions.isLoading ? (
            <p className="text-sm text-gray-500">Loading sessions\u2026</p>
          ) : sessions.isError ? (
            <p className="text-sm text-red-600">
              Failed to load sessions.
            </p>
          ) : (
            <table className="w-full text-left">
              <thead>
                <tr className="border-b text-sm font-medium text-gray-600">
                  <th className="p-3">Device / Browser</th>
                  <th className="p-3">IP</th>
                  <th className="p-3">Last Used</th>
                  <th className="p-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {sessions.data?.map((s) => (
                  <SessionRow key={s.id} session={s} />
                ))}
              </tbody>
            </table>
          )}
          <div className="mt-6 border-t pt-4">
            <Button
              variant="outline"
              disabled={logoutEverywhere.isPending}
              onClick={() => {
                if (
                  window.confirm(
                    'Are you sure you want to log out of all devices?',
                  )
                ) {
                  logoutEverywhere.mutate()
                }
              }}
            >
              {logoutEverywhere.isPending
                ? 'Logging out\u2026'
                : 'Log out everywhere'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
