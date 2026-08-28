/**
 * TeleTips Pro — Custom Clerk Appearance Theme
 * --------------------------------------------
 * Implements a modern dark glassmorphic theme with neon cyan & emerald accents
 * perfectly matched with the TeleTips Pro Dashboard.
 */

export const teletipsClerkAppearance = {
  layout: {
    socialButtonsPlacement: 'bottom',
    socialButtonsVariant: 'blockButton',
    showOptionalFields: false,
  },
  variables: {
    // Brand & Theme Colors
    colorPrimary: '#06b6d4',          // Neon Cyan
    colorSuccess: '#10b981',          // Emerald
    colorDanger: '#f43f5e',           // Rose
    colorWarning: '#f59e0b',          // Amber
    
    // Backgrounds & Surfaces
    colorBackground: '#0b0f19',       // Dark Space
    colorInputBackground: '#090d16',  // Deep Slate
    colorAlphaShade: '#1e293b',       // Border slate
    
    // Typography
    colorText: '#f8fafc',             // Pure White/Slate 50
    colorTextSecondary: '#94a3b8',    // Slate 400
    colorInputText: '#f8fafc',
    
    // Sizing & Borders
    borderRadius: '1rem',             // 16px rounded
    fontFamily: "'Cairo', 'Segoe UI', system-ui, sans-serif",
    fontSize: '0.875rem',
  },
  elements: {
    // Card & Modal Container
    card: {
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      backdropFilter: 'blur(20px)',
      border: '1px solid rgba(51, 65, 85, 0.65)',
      boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 30px -5px rgba(6, 182, 212, 0.15)',
      borderRadius: '1.5rem',
      padding: '2rem',
    },
    rootBox: {
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
    },
    
    // Header & Brand Logo
    headerTitle: {
      color: '#ffffff',
      fontSize: '1.25rem',
      fontWeight: '800',
      letterSpacing: '-0.025em',
    },
    headerSubtitle: {
      color: '#94a3b8',
      fontSize: '0.8125rem',
      lineHeight: '1.4',
    },
    
    // Primary Action Button (Gradient with Neon Cyan Glow)
    formButtonPrimary: {
      background: 'linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%)',
      color: '#ffffff',
      fontWeight: '700',
      fontSize: '0.875rem',
      borderRadius: '0.75rem',
      padding: '0.75rem 1.5rem',
      border: 'none',
      boxShadow: '0 4px 15px rgba(6, 182, 212, 0.3)',
      transition: 'all 0.2s ease',
      '&:hover': {
        background: 'linear-gradient(135deg, #4338ca 0%, #0891b2 100%)',
        boxShadow: '0 6px 20px rgba(6, 182, 212, 0.45)',
        transform: 'translateY(-1px)',
      },
      '&:active': {
        transform: 'scale(0.98)',
      },
    },
    
    // Input Fields
    formFieldInput: {
      backgroundColor: '#090d16',
      borderColor: 'rgba(51, 65, 85, 0.8)',
      color: '#f8fafc',
      borderRadius: '0.75rem',
      fontSize: '0.875rem',
      padding: '0.75rem 1rem',
      transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
      '&:focus': {
        borderColor: '#06b6d4',
        boxShadow: '0 0 0 2px rgba(6, 182, 212, 0.25)',
      },
    },
    formFieldLabel: {
      color: '#cbd5e1',
      fontSize: '0.75rem',
      fontWeight: '600',
      marginBottom: '0.25rem',
    },
    
    // Social Authentication Buttons (Google, GitHub, etc.)
    socialButtonsBlockButton: {
      backgroundColor: '#0f172a',
      borderColor: 'rgba(51, 65, 85, 0.8)',
      color: '#e2e8f0',
      borderRadius: '0.75rem',
      padding: '0.625rem 1rem',
      fontSize: '0.8125rem',
      fontWeight: '600',
      transition: 'all 0.15s ease',
      '&:hover': {
        backgroundColor: '#1e293b',
        borderColor: '#06b6d4',
        color: '#ffffff',
      },
    },
    socialButtonsBlockButtonText: {
      fontWeight: '600',
    },
    
    // Divider
    dividerLine: {
      backgroundColor: 'rgba(51, 65, 85, 0.5)',
    },
    dividerText: {
      color: '#64748b',
      fontSize: '0.75rem',
      textTransform: 'uppercase',
      fontWeight: '600',
    },
    
    // Footer Links & Terms
    footerActionLink: {
      color: '#38bdf8',
      fontWeight: '700',
      textDecoration: 'none',
      '&:hover': {
        color: '#06b6d4',
        textDecoration: 'underline',
      },
    },
    footerActionText: {
      color: '#94a3b8',
      fontSize: '0.8125rem',
    },
    
    // Identity Preview (Switch Accounts / User Badge)
    identityPreview: {
      backgroundColor: '#090d16',
      borderColor: 'rgba(51, 65, 85, 0.8)',
      borderRadius: '0.75rem',
    },
    identityPreviewText: {
      color: '#f8fafc',
    },
    
    // User Button Popup Menu
    userButtonPopoverCard: {
      backgroundColor: '#0f172a',
      borderColor: '#1e293b',
      boxShadow: '0 20px 40px rgba(0, 0, 0, 0.7)',
      borderRadius: '1rem',
    },
  },
};
