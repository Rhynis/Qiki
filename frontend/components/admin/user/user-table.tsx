import { ShieldCheck, UserCog } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { AdminUser } from '@/lib/api/admin'
import type { UserRole } from '@/lib/api/auth'
import { formatDate, formatPhone } from '@/lib/utils/format'

type UserTableProps = {
  users: AdminUser[]
  currentUserId?: string
  isLoading: boolean
  isUpdating: boolean
  onRoleChange: (user: AdminUser, role: UserRole) => void
  onStatusChange: (user: AdminUser, isActive: boolean) => void
}

const roleLabels: Record<UserRole, string> = {
  customer: 'Khách hàng',
  staff: 'Nhân viên',
  admin: 'Quản trị',
  driver: 'Tài xế',
}

export function UserTable({
  users,
  currentUserId,
  isLoading,
  isUpdating,
  onRoleChange,
  onStatusChange,
}: UserTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Người dùng</TableHead>
          <TableHead>Liên hệ</TableHead>
          <TableHead>Vai trò</TableHead>
          <TableHead>Trạng thái</TableHead>
          <TableHead>Ngày tạo</TableHead>
          <TableHead className="text-right">Thao tác</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {isLoading ? (
          <TableRow>
            <TableCell className="text-slate-600" colSpan={6}>
              Đang tải...
            </TableCell>
          </TableRow>
        ) : null}
        {users.map((user) => {
          const isSelf = user.id === currentUserId
          return (
            <TableRow key={user.id}>
              <TableCell>
                <div className="flex items-center gap-2 font-medium">
                  {user.role === 'admin' ? <ShieldCheck className="h-4 w-4 text-primary" /> : null}
                  {user.full_name || user.email}
                </div>
                <div className="text-sm text-slate-600">{user.email}</div>
              </TableCell>
              <TableCell>{user.phone ? formatPhone(user.phone) : 'Chưa có'}</TableCell>
              <TableCell>
                <select
                  className="h-9 rounded-md border bg-white px-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                  value={user.role}
                  disabled={isSelf || isUpdating}
                  onChange={(event) => onRoleChange(user, event.target.value as UserRole)}
                >
                  <option value="customer">{roleLabels.customer}</option>
                  <option value="staff">{roleLabels.staff}</option>
                  <option value="driver">{roleLabels.driver}</option>
                  <option value="admin">{roleLabels.admin}</option>
                </select>
              </TableCell>
              <TableCell>
                <Badge variant={user.is_active ? 'default' : 'outline'}>
                  {user.is_active ? 'Đang hoạt động' : 'Đã khóa'}
                </Badge>
              </TableCell>
              <TableCell>{formatDate(user.created_at, false)}</TableCell>
              <TableCell className="text-right">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isSelf || isUpdating}
                  onClick={() => onStatusChange(user, !user.is_active)}
                >
                  <UserCog className="h-4 w-4" />
                  {user.is_active ? 'Khóa' : 'Mở'}
                </Button>
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
