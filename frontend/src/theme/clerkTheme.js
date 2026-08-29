/**
 * TeleTips Pro — Custom Clerk Appearance Theme
 * --------------------------------------------
 * Implements a modern dark glassmorphic theme with neon cyan & emerald accents
 * perfectly matched with the TeleTips Pro Dashboard.
 */

export const teletipsClerkAppearance = {
  layout: {
    socialButtonsPlacement: 'top',
    socialButtonsVariant: 'blockButton',
    showOptionalFields: false,
  },
  variables: {
    // Brand & Theme Colors
    colorPrimary: '#00e5ff',          // Neon Cyan
    colorSuccess: '#10b981',          // Emerald
    colorDanger: '#f43f5e',           // Rose
    colorWarning: '#f59e0b',          // Amber
    
    // Backgrounds & Surfaces
    colorBackground: '#0b0f17',       // Main Background
    colorInputBackground: '#151c28',  // Card Background
    colorAlphaShade: '#1c2536',       // Button Base
    
    // Typography
    colorText: '#ffffff',             // Pure White
    colorTextSecondary: '#94a3b8',    // Muted Slate
    colorInputText: '#ffffff',
    
    // Sizing & Borders
    borderRadius: '1rem',
    fontFamily: "'Tajawal', 'Readex Pro', system-ui, sans-serif",
    fontSize: '0.875rem',
  },
  elements: {
    // Card & Modal Container
    card: {
      backgroundColor: 'rgba(21, 28, 40, 0.92)',
      backdropFilter: 'blur(20px)',
      border: '1px solid rgba(255, 255, 255, 0.08)',
      boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.8), 0 0 30px -5px rgba(0, 229, 255, 0.2)',
      borderRadius: '1.5rem',
      padding: '2rem',
    },
    rootBox: {
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      width: '100%',
    },
    
    // Header & Brand Logo
    headerTitle: {
      color: '#ffffff',
      fontSize: '1.35rem',
      fontWeight: '800',
      fontFamily: "'Tajawal', sans-serif",
    },
    headerSubtitle: {
      color: '#94a3b8',
      fontSize: '0.85rem',
      lineHeight: '1.5',
      fontFamily: "'Tajawal', sans-serif",
    },
    
    // Social Buttons
    socialButtonsBlockButton: {
      backgroundColor: '#1c2536',
      border: '1px solid rgba(255, 255, 255, 0.08)',
      color: '#ffffff',
      borderRadius: '0.75rem',
      fontWeight: '600',
      transition: 'all 0.2s ease',
      '&:hover': {
        backgroundColor: '#263248',
        borderColor: 'rgba(0, 229, 255, 0.4)',
        boxShadow: '0 0 15px rgba(0, 229, 255, 0.2)',
      },
    },

    // Primary Action Button (Gradient with Neon Cyan Glow)
    formButtonPrimary: {
      background: 'linear-gradient(135deg, #0099b8 0%, #00e5ff 100%)',
      color: '#0b0f17',
      fontWeight: '800',
      fontSize: '0.9rem',
      borderRadius: '0.75rem',
      padding: '0.75rem 1.5rem',
      border: 'none',
      boxShadow: '0 0 20px rgba(0, 229, 255, 0.4)',
      transition: 'all 0.2s ease',
      fontFamily: "'Tajawal', sans-serif",
      '&:hover': {
        background: 'linear-gradient(135deg, #00b4d8 0%, #33ebff 100%)',
        boxShadow: '0 0 30px rgba(0, 229, 255, 0.6)',
        transform: 'translateY(-1px)',
      },
      '&:active': {
        transform: 'scale(0.98)',
      },
    },
    
    // Input Fields
    formFieldInput: {
      backgroundColor: '#151c28',
      borderColor: 'rgba(255, 255, 255, 0.08)',
      color: '#ffffff',
      borderRadius: '0.75rem',
      fontSize: '0.875rem',
      padding: '0.75rem 1rem',
      transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
      '&:focus': {
        borderColor: '#00e5ff',
        boxShadow: '0 0 0 2px rgba(0, 229, 255, 0.3)',
      },
    },
    formFieldLabel: {
      color: '#94a3b8',
      fontSize: '0.8125rem',
      fontWeight: '600',
      fontFamily: "'Tajawal', sans-serif",
      marginBottom: '0.25rem',
    },
    
    // Social Authentication Buttons (Google, Discord, Facebook)
    socialButtonsBlockButton: {
      backgroundColor: '#1c2536',
      border: '1px solid rgba(255, 255, 255, 0.08)',
      color: '#ffffff',
      borderRadius: '0.75rem',
      padding: '0.625rem 1rem',
      fontSize: '0.875rem',
      fontWeight: '600',
      fontFamily: "'Tajawal', sans-serif",
      transition: 'all 0.2s ease',
      '&:hover': {
        backgroundColor: '#263248',
        borderColor: 'rgba(0, 229, 255, 0.4)',
        boxShadow: '0 0 15px rgba(0, 229, 255, 0.2)',
        color: '#ffffff',
      },
    },
    socialButtonsBlockButtonText: {
      fontWeight: '600',
      fontFamily: "'Tajawal', sans-serif",
    },
    
    // Divider
    dividerLine: {
      backgroundColor: 'rgba(255, 255, 255, 0.08)',
    },
    dividerText: {
      color: '#94a3b8',
      fontSize: '0.75rem',
      fontWeight: '600',
      fontFamily: "'Tajawal', sans-serif",
    },
    
    // Footer Links & Terms
    footerActionLink: {
      color: '#00e5ff',
      fontWeight: '700',
      fontFamily: "'Tajawal', sans-serif",
      textDecoration: 'none',
      '&:hover': {
        color: '#33ebff',
        textDecoration: 'underline',
      },
    },
    footerActionText: {
      color: '#94a3b8',
      fontSize: '0.8125rem',
      fontFamily: "'Tajawal', sans-serif",
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
