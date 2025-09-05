import React, { createContext, useContext } from 'react';
import { useTrayBehavior } from '../hooks/useTrayBehavior';

interface TrayContextType {
  minimizeToTray: boolean;
  toggleMinimizeToTray: (enabled: boolean) => void;
  showMainWindow: () => Promise<void>;
  hideToTray: () => Promise<void>;
}

const TrayContext = createContext<TrayContextType | undefined>(undefined);

export const TrayProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const trayBehavior = useTrayBehavior();
  
  return (
    <TrayContext.Provider value={trayBehavior}>
      {children}
    </TrayContext.Provider>
  );
};

export const useTray = () => {
  const context = useContext(TrayContext);
  if (context === undefined) {
    throw new Error('useTray must be used within a TrayProvider');
  }
  return context;
};