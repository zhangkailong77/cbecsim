export type WarehouseModeKey = 'official' | 'third_party' | 'self_built';
export type WarehouseLocationKey = 'near_kl' | 'far_kl';

export interface BuyerZone {
  zoneCode: string;
  zoneName: string;
  lngLat: [number, number];
  orderShare: number;
  avgOrderValue: number;
  slaSensitivity: number;
  distanceFactor: number;
}

export interface ZoneForecastRow {
  zoneCode: string;
  zoneName: string;
  orderShare: number;
  avgOrderValue: number;
  etaDays: number;
  overdueRate: number;
  refundRisk: number;
}

export interface ZoneForecastSummary {
  avgDeliveryDays: number;
  overdueRate: number;
  refundRisk: number;
  expectedRating: number;
  zoneRows: ZoneForecastRow[];
}

export const BUYER_ZONES_MY: BuyerZone[] = [
  {
    zoneCode: 'kl_core',
    zoneName: '吉隆坡核心区',
    lngLat: [101.6869, 3.139],
    orderShare: 0.28,
    avgOrderValue: 94,
    slaSensitivity: 0.95,
    distanceFactor: 0.86,
  },
  {
    zoneCode: 'cheras_east',
    zoneName: '蕉赖东区',
    lngLat: [101.746, 3.093],
    orderShare: 0.18,
    avgOrderValue: 88,
    slaSensitivity: 0.9,
    distanceFactor: 0.98,
  },
  {
    zoneCode: 'pj_west',
    zoneName: '八打灵西区',
    lngLat: [101.618, 3.106],
    orderShare: 0.17,
    avgOrderValue: 86,
    slaSensitivity: 0.84,
    distanceFactor: 1.05,
  },
  {
    zoneCode: 'subang_north',
    zoneName: '梳邦北区',
    lngLat: [101.57, 3.182],
    orderShare: 0.14,
    avgOrderValue: 90,
    slaSensitivity: 0.8,
    distanceFactor: 1.12,
  },
  {
    zoneCode: 'kajang_south',
    zoneName: '加影南区',
    lngLat: [101.781, 2.992],
    orderShare: 0.12,
    avgOrderValue: 92,
    slaSensitivity: 0.76,
    distanceFactor: 1.22,
  },
  {
    zoneCode: 'klang_port_west',
    zoneName: '巴生港西区',
    lngLat: [101.397, 3.001],
    orderShare: 0.11,
    avgOrderValue: 84,
    slaSensitivity: 0.71,
    distanceFactor: 1.28,
  },
];

function clamp(v: number, min: number, max: number) {
  return Math.min(max, Math.max(min, v));
}

function getBaseEtaDays(mode: WarehouseModeKey, location: WarehouseLocationKey) {
  const modeDelta: Record<WarehouseModeKey, number> = {
    official: -0.08,
    third_party: 0.26,
    self_built: -0.03,
  };
  const locationBase: Record<WarehouseLocationKey, number> = {
    near_kl: 1.55,
    far_kl: 2.45,
  };
  return Math.max(0.8, locationBase[location] + modeDelta[mode]);
}

export function calcZoneForecast(mode: WarehouseModeKey, location: WarehouseLocationKey): ZoneForecastSummary {
  const baseEta = getBaseEtaDays(mode, location);
  const zoneRows: ZoneForecastRow[] = BUYER_ZONES_MY.map((zone) => {
    const etaDays = baseEta * zone.distanceFactor;
    const overdue = clamp((etaDays - 2.0) * 0.22 * zone.slaSensitivity, 0.01, 0.78);
    const refund = clamp(overdue * (0.2 + zone.slaSensitivity * 0.28), 0.004, 0.35);
    return {
      zoneCode: zone.zoneCode,
      zoneName: zone.zoneName,
      orderShare: zone.orderShare,
      avgOrderValue: zone.avgOrderValue,
      etaDays,
      overdueRate: overdue,
      refundRisk: refund,
    };
  });

  const avgDeliveryDays = zoneRows.reduce((sum, row) => sum + row.etaDays * row.orderShare, 0);
  const overdueRate = zoneRows.reduce((sum, row) => sum + row.overdueRate * row.orderShare, 0);
  const refundRisk = zoneRows.reduce((sum, row) => sum + row.refundRisk * row.orderShare, 0);
  const expectedRating = clamp(5 - overdueRate * 1.9 - refundRisk * 2.2, 3.2, 4.95);

  return {
    avgDeliveryDays,
    overdueRate,
    refundRisk,
    expectedRating,
    zoneRows,
  };
}

export function simulateDailyOrdersByZone(
  mode: WarehouseModeKey,
  location: WarehouseLocationKey,
  runId: number,
  daySeed: number,
) {
  const forecast = calcZoneForecast(mode, location);
  const demandBase = 120 + (runId % 9) * 7 + (daySeed % 6) * 5;
  const rows = forecast.zoneRows.map((zone, idx) => {
    const jitter = ((runId + daySeed + idx * 3) % 7) / 100;
    const orders = Math.max(1, Math.round(demandBase * zone.orderShare * (1 + jitter - zone.overdueRate * 0.35)));
    const gmv = Math.round(orders * zone.avgOrderValue);
    const refunds = Math.round(orders * zone.refundRisk);
    return {
      zoneCode: zone.zoneCode,
      zoneName: zone.zoneName,
      orders,
      gmv,
      refunds,
      overdueRate: zone.overdueRate,
    };
  });
  const totalOrders = rows.reduce((sum, r) => sum + r.orders, 0);
  const totalGmv = rows.reduce((sum, r) => sum + r.gmv, 0);
  const totalRefunds = rows.reduce((sum, r) => sum + r.refunds, 0);
  return {
    rows,
    totalOrders,
    totalGmv,
    totalRefunds,
    forecast,
  };
}
