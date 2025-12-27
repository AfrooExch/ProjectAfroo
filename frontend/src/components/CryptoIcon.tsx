'use client';

import { FC } from 'react';
import * as Web3Icons from '@web3icons/react';

interface CryptoIconProps {
  symbol: string;
  size?: number;
  variant?: 'branded' | 'mono';
}

const CryptoIcon: FC<CryptoIconProps> = ({ symbol, size = 24, variant = 'branded' }) => {
  const normalizedSymbol = symbol.split('-')[0].toUpperCase();
  const componentName = `Token${normalizedSymbol}` as keyof typeof Web3Icons;
  const IconComponent = Web3Icons[componentName] as any;

  if (IconComponent && typeof IconComponent === 'function') {
    return <IconComponent size={size} variant={variant} />;
  }

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'white',
        fontSize: size * 0.4,
        fontWeight: 'bold'
      }}
    >
      {normalizedSymbol.substring(0, 2)}
    </div>
  );
};

export default CryptoIcon;
