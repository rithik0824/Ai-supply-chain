import { useState, useEffect } from 'react';
import axios from 'axios';
import { AlertTriangle, CheckCircle } from 'lucide-react';

export default function Inventory() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    axios.get('/api/inventory')
      .then(res => {
        if (isMounted) setItems(res.data);
      })
      .catch(err => {
        console.error(err);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  if (loading) return <div style={{ padding: '2rem' }}>Loading inventory data from CSV...</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: '600', marginBottom: '0.5rem', fontFamily: 'Outfit' }}>Inventory Dataset</h1>
          <p style={{ color: 'var(--text-secondary)' }}>Viewing active records directly from retail_store_inventory.csv</p>
        </div>
      </div>

      <div className="glass-panel" style={{ overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              <th style={{ padding: '1.5rem', fontWeight: '500', color: 'var(--text-secondary)' }}>Product ID / Category</th>
              <th style={{ padding: '1.5rem', fontWeight: '500', color: 'var(--text-secondary)' }}>Current Stock Level</th>
              <th style={{ padding: '1.5rem', fontWeight: '500', color: 'var(--text-secondary)' }}>Demand Forecast</th>
              <th style={{ padding: '1.5rem', fontWeight: '500', color: 'var(--text-secondary)' }}>Risk Status</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '1.5rem', fontWeight: '500' }}>{item.item_name}</td>
                <td style={{ padding: '1.5rem' }}>{item.current_stock} units</td>
                <td style={{ padding: '1.5rem' }}>{item.demand_forecast} predicted</td>
                <td style={{ padding: '1.5rem' }}>
                  {item.stockout_risk ? (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', color: 'var(--danger)', padding: '0.25rem 0.75rem', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '2rem', fontSize: '0.875rem', fontWeight: '500' }}>
                      <AlertTriangle size={14} />
                      High Risk
                    </span>
                  ) : (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', color: 'var(--success)', padding: '0.25rem 0.75rem', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '2rem', fontSize: '0.875rem', fontWeight: '500' }}>
                      <CheckCircle size={14} />
                      Stable
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan="4" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  No inventory records found in the CSV dataset.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
