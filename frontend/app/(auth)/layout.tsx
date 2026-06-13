export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto flex min-h-[calc(100vh-73px)] max-w-md items-center px-4 py-12">
      <div className="w-full rounded-lg border bg-white p-6 shadow-sm">
        <div className="mb-6 text-center">
          <p className="text-lg font-semibold text-primary">Gas Quốc Cường</p>
          <p className="text-sm text-slate-500">Mua gas LPG an toàn, nhanh chóng</p>
        </div>
        {children}
        <p className="mx-auto mt-6 max-w-72 text-balance text-center text-xs text-slate-500">
          Bảo mật tài khoản bằng mật khẩu mạnh
          <br />
          và không chia sẻ thông tin đăng nhập.
        </p>
      </div>
    </div>
  )
}
