import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { formatDate } from '@/lib/utils';
import { Users, Search, Trash2, ShieldCheck, UserX, UserCheck, UserPlus } from 'lucide-react';

interface AdminUser {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  printer_count: number;
  created_at: string;
}

function RoleBadge({ role }: { role: string }) {
  const styles = role === 'owner'
    ? 'bg-primary/10 text-primary'
    : 'bg-muted text-muted-foreground';
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${styles}`}>
      {role === 'owner' && <ShieldCheck className="h-3 w-3" />}
      {role === 'owner' ? 'Owner' : 'Print Person'}
    </span>
  );
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${active ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>
      {active ? <UserCheck className="h-3 w-3" /> : <UserX className="h-3 w-3" />}
      {active ? 'Active' : 'Inactive'}
    </span>
  );
}

function ConfirmDialog({ message, onConfirm, onCancel }: { message: string; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="rounded-lg border bg-card p-6 shadow-xl max-w-sm w-full mx-4 space-y-4">
        <p className="font-medium">{message}</p>
        <div className="flex gap-2">
          <Button size="sm" variant="destructive" onClick={onConfirm}>Confirm</Button>
          <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
        </div>
      </div>
    </div>
  );
}

function AddUserForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ email: '', full_name: '', password: '', role: 'owner' });
  const [showPass, setShowPass] = useState(false);

  const set = (f: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(p => ({ ...p, [f]: e.target.value }));

  const create = useMutation({
    mutationFn: () => api.post('/admin/users', form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] });
      qc.invalidateQueries({ queryKey: ['admin-stats'] });
      onDone();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.email || !form.full_name || !form.password) return;
    create.mutate();
  };

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border bg-muted/30 p-5 space-y-4">
      <h3 className="font-semibold text-sm">New User</h3>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label htmlFor="new-full-name">Full Name *</Label>
          <Input
            id="new-full-name"
            placeholder="Jane Doe"
            value={form.full_name}
            onChange={set('full_name')}
            autoComplete="off"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="new-email">Email *</Label>
          <Input
            id="new-email"
            type="email"
            placeholder="jane@example.com"
            value={form.email}
            onChange={set('email')}
            autoComplete="off"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="new-password">Password *</Label>
          <div className="relative">
            <Input
              id="new-password"
              type={showPass ? 'text' : 'password'}
              placeholder="Min. 8 characters"
              value={form.password}
              onChange={set('password')}
              className="pr-16"
              autoComplete="new-password"
            />
            <button
              type="button"
              onClick={() => setShowPass(v => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground hover:text-foreground"
            >
              {showPass ? 'Hide' : 'Show'}
            </button>
          </div>
        </div>
        <div className="space-y-1">
          <Label htmlFor="new-role">Role *</Label>
          <select
            id="new-role"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={form.role}
            onChange={set('role')}
          >
            <option value="owner">Owner — full access</option>
            <option value="print_person">Print Person — limited access</option>
          </select>
        </div>
      </div>
      {create.isError && (
        <p className="text-sm text-destructive">
          {(create.error as any)?.response?.data?.detail || 'Failed to create user'}
        </p>
      )}
      <div className="flex gap-2">
        <Button
          type="submit"
          size="sm"
          disabled={!form.email || !form.full_name || !form.password || create.isPending}
          isLoading={create.isPending}
        >
          Create User
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </form>
  );
}

export default function AdminUsersPage() {
  const qc = useQueryClient();
  const { user: currentUser } = useAuth();
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['admin-users', search, roleFilter, activeFilter],
    queryFn: () => {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      if (roleFilter) params.set('role', roleFilter);
      if (activeFilter !== '') params.set('is_active', activeFilter);
      return api.get(`/admin/users?${params}`).then(r => r.data.data as AdminUser[]);
    },
  });

  const patchUser = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<Pick<AdminUser, 'role' | 'is_active'>> }) =>
      api.patch(`/admin/users/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  });

  const deleteUser = useMutation({
    mutationFn: (id: number) => api.delete(`/admin/users/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] });
      qc.invalidateQueries({ queryKey: ['admin-stats'] });
      setDeleteTarget(null);
    },
  });

  const isSelf = (u: AdminUser) => u.id === currentUser?.id;

  return (
    <div className="max-w-5xl space-y-6">
      {deleteTarget && (
        <ConfirmDialog
          message={`Delete user "${deleteTarget.full_name}" (${deleteTarget.email})? This cannot be undone and will remove all their data.`}
          onConfirm={() => deleteUser.mutate(deleteTarget.id)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Users className="h-6 w-6 text-primary" />
            User Management
          </h1>
          <p className="text-sm text-muted-foreground mt-1">Manage accounts, roles, and access</p>
        </div>
        <Button onClick={() => setShowAddForm(v => !v)}>
          <UserPlus className="mr-2 h-4 w-4" />
          Add User
        </Button>
      </div>

      {showAddForm && <AddUserForm onDone={() => setShowAddForm(false)} />}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search by name or email..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <select
          className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          value={roleFilter}
          onChange={e => setRoleFilter(e.target.value)}
        >
          <option value="">All roles</option>
          <option value="owner">Owner</option>
          <option value="print_person">Print Person</option>
        </select>
        <select
          className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          value={activeFilter}
          onChange={e => setActiveFilter(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-lg border bg-card overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground">Loading users...</div>
        ) : !data || data.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground">
            <Users className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p>No users found</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left">User</th>
                <th className="px-4 py-3 text-left">Role</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-right">Printers</th>
                <th className="px-4 py-3 text-left">Joined</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.map(u => (
                <tr key={u.id} className={`hover:bg-muted/30 ${isSelf(u) ? 'bg-primary/5' : ''}`}>
                  <td className="px-4 py-3">
                    <div>
                      <p className="font-medium">{u.full_name} {isSelf(u) && <span className="text-xs text-muted-foreground">(you)</span>}</p>
                      <p className="text-xs text-muted-foreground">{u.email}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {isSelf(u) ? (
                      <RoleBadge role={u.role} />
                    ) : (
                      <select
                        className="rounded border border-border bg-background px-2 py-1 text-xs"
                        value={u.role}
                        onChange={e => patchUser.mutate({ id: u.id, body: { role: e.target.value } })}
                        disabled={patchUser.isPending}
                      >
                        <option value="owner">Owner</option>
                        <option value="print_person">Print Person</option>
                      </select>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge active={u.is_active} />
                  </td>
                  <td className="px-4 py-3 text-right text-muted-foreground">{u.printer_count}</td>
                  <td className="px-4 py-3 text-muted-foreground">{formatDate(u.created_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1">
                      {!isSelf(u) && (
                        <>
                          <button
                            onClick={() => patchUser.mutate({ id: u.id, body: { is_active: !u.is_active } })}
                            disabled={patchUser.isPending}
                            title={u.is_active ? 'Deactivate user' : 'Activate user'}
                            className={`p-1.5 rounded transition-colors ${u.is_active ? 'text-muted-foreground hover:text-yellow-600' : 'text-muted-foreground hover:text-green-600'}`}
                          >
                            {u.is_active ? <UserX className="h-4 w-4" /> : <UserCheck className="h-4 w-4" />}
                          </button>
                          <button
                            onClick={() => setDeleteTarget(u)}
                            title="Delete user"
                            className="p-1.5 rounded text-muted-foreground hover:text-destructive transition-colors"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <p className="text-xs text-muted-foreground">
        {data?.length ?? 0} user{data?.length !== 1 ? 's' : ''} shown.
        Role changes and deactivation take effect immediately.
      </p>
    </div>
  );
}
