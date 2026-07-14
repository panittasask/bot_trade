# Roadmap การพัฒนา TradeLab

เอกสารนี้กำหนดลำดับงานต่อจากรุ่นปัจจุบัน เป้าหมายคือพัฒนาจากระบบ Real Market Data + Paper Trading ให้เป็นระบบที่ทดสอบย้อนหลังได้ เชื่อม Paper Broker ได้อย่างปลอดภัย และมีข้อมูลเพียงพอสำหรับตัดสินใจว่าจะพัฒนาต่อไปสู่ Live Trading หรือไม่

## สถานะปัจจุบัน

- `BTC/USD` และ `ETH/USD` รับราคาจริงจาก Kraken Spot WebSocket
- `AAPL` และ `SPY` ยังใช้ราคา Synthetic
- กลยุทธ์ SMA crossover พร้อม Stop loss และ Take profit
- ส่งคำสั่งผ่าน Paper Broker ภายในระบบเท่านั้น
- มี Dashboard, SQLite persistence, WebSocket updates และ automated tests
- มี reconnect และ stale-data guard สำหรับข้อมูลคริปโต

## หลักการพัฒนา

1. ยังไม่เปิด Live Trading จนกว่าจะผ่าน Backtest และ Paper Trading ตามเกณฑ์
2. แยก Market Data, Strategy, Risk และ Broker ออกจากกันให้ทดสอบได้
3. ทุกคำสั่งต้องผ่าน Risk Engine ก่อนถึง Broker
4. เมื่อข้อมูลผิดปกติหรือสถานะ Broker ไม่ตรงกัน ระบบต้องหยุดเปิดสถานะใหม่
5. ห้ามเก็บ API secret ใน source code หรือ Git

## Phase 1 — Backtesting Engine

เป้าหมาย: วัดผลกลยุทธ์จากข้อมูลย้อนหลังโดยใช้ logic เดียวกับระบบ Paper Trading

งานหลัก:

- สร้าง interface กลางสำหรับ Market Data และ Strategy
- รองรับ historical OHLCV จากไฟล์ CSV และ provider adapter
- เพิ่ม event-driven backtest เพื่อป้องกัน look-ahead bias
- จำลองค่าธรรมเนียม, spread และ slippage
- คำนวณ Equity curve, realized/unrealized P/L และ drawdown
- แสดงผล Backtest บน Dashboard
- Export ผลเป็น CSV หรือ JSON

ตัวชี้วัดที่ต้องมี:

- Total return
- Maximum drawdown
- Win rate
- Profit factor
- Sharpe ratio
- จำนวนคำสั่งและเวลาเฉลี่ยที่ถือสถานะ

เกณฑ์ส่งมอบ:

- ผลลัพธ์เดิมต้องทำซ้ำได้เมื่อใช้ข้อมูลและ config เดิม
- ไม่มีการใช้ข้อมูลแท่งอนาคตในการสร้างสัญญาณ
- มี unit tests สำหรับ fees, slippage, fills และ metrics
- ผู้ใช้เลือกรอบเวลาและ config แล้วรัน Backtest จาก Dashboard ได้

## Phase 2 — Strategy Framework

เป้าหมาย: เพิ่มหรือเปรียบเทียบกลยุทธ์ได้โดยไม่แก้ Trading Engine

งานหลัก:

- สร้าง Strategy protocol หรือ base class
- ย้าย SMA crossover เป็น strategy plugin ตัวแรก
- เพิ่ม EMA crossover และ RSI mean reversion
- รองรับ parameter presets
- เพิ่ม validation แยกตามกลยุทธ์
- เปรียบเทียบหลาย strategy/config บนข้อมูลชุดเดียวกัน

เกณฑ์ส่งมอบ:

- เพิ่ม strategy ใหม่ได้โดยไม่แก้ Broker หรือ Risk Engine
- Strategy ไม่สามารถส่งคำสั่งข้าม Risk Engine
- Backtest และ Paper Trading ใช้ strategy implementation ชุดเดียวกัน

## Phase 3 — Real Stock Market Data

เป้าหมาย: เปลี่ยน `AAPL` และ `SPY` จากข้อมูล Synthetic เป็นข้อมูลตลาดจริง

งานหลัก:

- สร้าง stock market-data adapter
- รองรับ market hours, holidays และ timezone ของตลาดหุ้นสหรัฐฯ
- แสดง delayed/real-time status ให้ชัดเจนตามสิทธิ์ของ data plan
- ตรวจ missing bars, duplicate events และ out-of-order timestamps
- หยุดเปิดสถานะเมื่อ feed stale หรือ market ปิด
- เก็บ source และ timestamp ของราคาที่ใช้ตัดสินใจทุกคำสั่ง

เกณฑ์ส่งมอบ:

- Dashboard ไม่แสดงข้อมูล delayed ว่าเป็น real-time
- ไม่มีคำสั่งหุ้นนอกเวลาที่กำหนดโดยไม่ตั้งใจ
- Feed disconnect แล้วระบบเข้าสู่ `DATA WAIT` และไม่เปิดสถานะใหม่

## Phase 4 — Alpaca Paper Broker

เป้าหมาย: ส่งคำสั่งไปบัญชี Paper ของโบรกเกอร์ โดยยังไม่ใช้เงินจริง

งานหลัก:

- สร้าง Broker interface และ Alpaca Paper adapter
- รองรับ market order และ fractional quantity
- เพิ่ม client order ID เพื่อป้องกันคำสั่งซ้ำ
- ติดตาม lifecycle: submitted, accepted, partially filled, filled, canceled, rejected
- ทำ order/position reconciliation เมื่อเปิดโปรแกรมและหลัง reconnect
- แยก internal paper broker กับ external paper broker ผ่าน config
- เพิ่มปุ่ม Cancel open orders และ Close all paper positions

เกณฑ์ส่งมอบ:

- Restart โปรแกรมแล้วสถานะ order/position ตรงกับ Broker
- Network retry ไม่ทำให้เกิดคำสั่งซ้ำ
- คำสั่ง rejected และ partially filled แสดงบน Dashboard ถูกต้อง
- ไม่มี endpoint หรือ config ที่เปิด Live Broker โดยค่าเริ่มต้น

## Phase 5 — Risk Engine และ Kill Switch

เป้าหมาย: จำกัดความเสียหายจากกลยุทธ์ ข้อมูล หรือระบบผิดพลาด

งานหลัก:

- Daily loss limit
- Maximum drawdown limit
- Maximum order notional และ maximum total exposure
- จำกัดจำนวนคำสั่งต่อนาทีและต่อวัน
- จำกัด exposure แยกตามสินทรัพย์และ asset class
- Reject ราคาที่กระโดดผิดปกติหรือข้อมูลเก่า
- Circuit breaker เมื่อเกิด rejected orders ต่อเนื่อง
- Global kill switch: หยุดกลยุทธ์ ยกเลิก order และเลือกปิดสถานะ
- บันทึกเหตุผลของทุก risk rejection

เกณฑ์ส่งมอบ:

- มี automated tests ครอบคลุม risk rule ทุกข้อ
- Strategy ไม่สามารถ bypass risk checks
- Kill switch ทำงานได้แม้ strategy task เกิด exception
- Dashboard แสดงเหตุผลที่ระบบหยุดและวิธีกู้คืน

## Phase 6 — Dashboard และ Operations

เป้าหมาย: ทำให้ตรวจสอบและแก้ปัญหาระบบได้จากหน้าจอเดียว

งานหลัก:

- Candlestick chart พร้อม SMA/EMA/RSI overlays
- หน้า Positions, Orders, Fills และ Strategy logs
- แสดง Feed latency, last update และ reconnect count
- แสดง Broker connection และ reconciliation status
- Alerts สำหรับ feed stale, risk halt, rejected order และ drawdown
- Filter ประวัติตามสินทรัพย์และช่วงเวลา
- Download trade journal และ Backtest report
- แยกสถานะ `RUNNING`, `PAUSED`, `DATA WAIT`, `RISK HALT` และ `ERROR`

เกณฑ์ส่งมอบ:

- ผู้ใช้ระบุสาเหตุที่บอทไม่เทรดได้จาก Dashboard
- UI แสดง source และ timestamp ของข้อมูลทุกตลาด
- รองรับ desktop และ mobile โดยไม่มีข้อมูลสำคัญหาย

## Phase 7 — Security และ Configuration

เป้าหมาย: ป้องกัน secret รั่วและการควบคุมระบบโดยไม่ได้รับอนุญาต

งานหลัก:

- Login และ session management
- แยก viewer กับ operator permissions
- เก็บ secrets ผ่าน environment หรือ secret manager
- ปิด API ควบคุมจาก network ภายนอกโดยค่าเริ่มต้น
- CSRF protection และ rate limiting สำหรับ control endpoints
- Audit log สำหรับ start, stop, config, reset และ order actions
- ตรวจ config ก่อน startup และ redact secrets จาก logs

เกณฑ์ส่งมอบ:

- Secret scanning ผ่านก่อน merge
- ผู้ใช้แบบ viewer ส่งคำสั่งควบคุมไม่ได้
- ทุก action สำคัญระบุเวลา ผู้ใช้ และผลลัพธ์ย้อนหลังได้

## Phase 8 — Deployment และ Monitoring

เป้าหมาย: รันระบบต่อเนื่องและกู้คืนได้เมื่อ process หรือเครื่องมีปัญหา

งานหลัก:

- Docker Compose พร้อม persistent volume
- Health, readiness และ market-data health endpoints
- Structured logs และ log rotation
- Metrics: feed age, order latency, error count และ portfolio drawdown
- Database backup และ restore procedure
- Graceful shutdown และ startup reconciliation
- CI pipeline สำหรับ tests, lint และ dependency audit
- Deployment guide สำหรับเครื่องส่วนตัวหรือ VPS

เกณฑ์ส่งมอบ:

- Restart container แล้วไม่สูญเสีย trade history
- Health check แยก app alive ออกจาก feed/broker readiness
- มี alert เมื่อ feed stale, process down หรือ risk halt
- ทดสอบ restore จาก backup สำเร็จ

## Phase 9 — Paper Trading Soak Test

เป้าหมาย: พิสูจน์ความเสถียรในสภาวะตลาดจริงก่อนพิจารณาเงินจริง

ระยะเวลาขั้นต่ำ: 2–4 สัปดาห์ โดยครอบคลุมตลาดผันผวนและช่วง reconnect

ข้อมูลที่ต้องเก็บ:

- Uptime และจำนวน reconnect
- Feed gaps และ stale events
- Order rejects, duplicate orders และ reconciliation mismatches
- Actual paper slippage เทียบกับ backtest
- Daily P/L, drawdown และ risk halts
- เหตุการณ์ที่ต้องแก้ด้วยมือ

เกณฑ์เบื้องต้นก่อนพิจารณา Live Trading:

- ไม่มี duplicate order
- ไม่มี position mismatch ที่ระบบแก้เองไม่ได้
- Feed หรือ Broker หลุดแล้วไม่เปิดคำสั่งจากข้อมูลเก่า
- Maximum drawdown ไม่เกินค่าที่กำหนดไว้ล่วงหน้า
- ระบบผ่าน restart/reconnect tests หลายครั้ง
- ผลลัพธ์ Paper ไม่แตกต่างจาก Backtest อย่างไม่มีคำอธิบาย

การผ่านเฟสนี้ไม่ได้แปลว่ากลยุทธ์จะทำกำไร และไม่ใช่คำแนะนำให้เริ่มใช้เงินจริง

## งานที่จะทำใน Sprint ถัดไป

ลำดับงานแนะนำสำหรับรอบถัดไป:

1. แยก `MarketDataProvider`, `Strategy` และ `Broker` interfaces
2. สร้าง OHLCV model และ historical CSV loader
3. สร้าง Backtest runner ที่ใช้ SMA strategy เดิม
4. เพิ่ม fees, spread และ slippage model
5. เพิ่ม performance metrics และ tests
6. เพิ่ม API เริ่ม Backtest และอ่านผล
7. เพิ่มหน้า Backtest results ใน Dashboard

Definition of Done ของ Sprint:

- รัน Backtest จากข้อมูลตัวอย่างได้ด้วยคำสั่งและ API
- ได้ Equity curve, trade list และ metrics ที่ทำซ้ำได้
- Tests เดิมทั้งหมดผ่านและมี tests สำหรับ Backtest เพิ่ม
- คู่มืออธิบายวิธีนำเข้าข้อมูลและอ่านผล

