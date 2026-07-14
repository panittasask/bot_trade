# TradeLab Paper Bot

บอทเทรดเพื่อการเรียนรู้และทดสอบกลยุทธ์ พร้อม dashboard แบบเรียลไทม์ โดย `BTC/USD` และ `ETH/USD` ใช้ราคา Kraken Spot จริง ส่วน `AAPL` และ `SPY` ยังใช้ราคาจำลอง ทุกคำสั่งเป็น Paper และ **ไม่ส่งคำสั่งซื้อขายด้วยเงินจริง**

## ฟีเจอร์

- กลยุทธ์ SMA crossover ปรับช่วงเส้นเร็ว/ช้าได้
- Risk controls: ขนาดคำสั่ง, สัดส่วนถือครองสูงสุด, stop loss และ take profit
- Paper portfolio พร้อม cash, equity, unrealized/realized P&L
- บันทึกคำสั่งและ equity curve ลง SQLite
- Dashboard responsive อัปเดตผ่าน WebSocket
- Public Kraken WebSocket v2 พร้อม reconnect และ stale-data guard (ไม่ต้องใช้ API key)
- API สำหรับ start, stop, reset, เปลี่ยนตลาด และปรับกลยุทธ์

## เริ่มใช้งาน

> คู่มือการใช้งาน Dashboard แบบละเอียด: [USER_GUIDE_TH.md](USER_GUIDE_TH.md)

ต้องมี Python 3.10 ขึ้นไป จาก PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8765
```

เปิด <http://127.0.0.1:8765> แล้วกด **Start bot** ระบบจะเก็บข้อมูล 22 ticks ก่อนเริ่มหาสัญญาณ SMA (ค่าเริ่มต้นประมาณ 44 วินาที)

รันชุดทดสอบ:

```powershell
pytest -q
```

หรือรันด้วย Docker:

```powershell
docker build -t tradelab .
docker run --rm -p 8000:8000 -v ${PWD}/data:/app/data tradelab
```

## API หลัก

| Method | Path | หน้าที่ |
|---|---|---|
| `GET` | `/api/status` | สถานะและข้อมูล portfolio ทั้งหมด |
| `POST` | `/api/start` | เริ่ม engine |
| `POST` | `/api/stop` | หยุด engine |
| `POST` | `/api/reset` | ล้าง paper portfolio และประวัติ |
| `PUT` | `/api/config` | ปรับ SMA และ risk parameters |
| `PUT` | `/api/symbol` | เปลี่ยนตลาดที่ติดตาม |
| `WS` | `/ws` | สตรีม snapshot ไปยัง dashboard |

## ก่อนเชื่อมเงินจริง

รุ่นนี้ใช้ข้อมูล Kraken Spot จริงเฉพาะคริปโต แต่ยังใช้ paper broker เพื่อความปลอดภัย หากจะต่อโบรกเกอร์ แนะนำเริ่มจากบัญชี paper ของ Alpaca ซึ่งแยก endpoint และ credentials ออกจากบัญชี live จากนั้นจึงเพิ่ม broker adapter โดยคง risk controls และ kill switch ไว้ ห้ามใส่ API secret ใน source code หรือ commit ลง Git

> ซอฟต์แวร์นี้เป็นเครื่องมือเพื่อการศึกษา ไม่ใช่คำแนะนำทางการเงิน ผลจากข้อมูลจำลองหรือ backtest ไม่รับประกันผลในตลาดจริง
