/**
 * Shared UI tokens and theme definitions for WebSync AI.
 */

export const BRAND_NAME = 'WebSync AI';

export const THEME_COLORS = {
  primary: '#3b82f6',
  primaryHover: '#2563eb',
  background: '#090d16',
  surface: '#111827',
  surfaceBorder: '#1f2937',
  textPrimary: '#f9fafb',
  textSecondary: '#9ca3af',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
} as const;

export interface NavItem {
  label: string;
  href: string;
  iconName: string;
  status: 'active' | 'planned';
}

export const NAVIGATION_ITEMS: NavItem[] = [
  { label: 'Overview', href: '/', iconName: 'Home', status: 'active' },
  { label: 'Workers', href: '/workers', iconName: 'Server', status: 'planned' },
  { label: 'Jobs', href: '/jobs', iconName: 'Cpu', status: 'planned' },
  { label: 'Resource Monitor', href: '/monitor', iconName: 'Activity', status: 'planned' },
  { label: 'Activity Logs', href: '/logs', iconName: 'FileText', status: 'planned' },
  { label: 'Settings', href: '/settings', iconName: 'Settings', status: 'planned' },
];
