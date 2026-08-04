const express = require('express');
const mysql = require('mysql2');
const bodyParser = require('body-parser');
const router = express.Router();

const db = mysql.createConnection({
    host: 'localhost',
    user: 'root',
    password: '你的数据库密码',
    database: 'wzyProjectDb'
});

router.use(bodyParser.json());

// 注册接口
router.post('/api/signup', (req, res) => {
    console.log('收到注册请求:', req.body); // 日志输出
    const { name, email, password } = req.body;
    if (!name || !email || !password) {
        console.error('字段缺失:', { name, email, password });
        return res.json({ success: false, message: '请填写所有字段' });
    }
    db.query('INSERT INTO user (email, name, password) VALUES (?, ?, ?)', [email, name, password], (err, result) => {
        if (err) {
            console.error('注册数据库错误:', err); // 日志输出
            if (err.code === 'ER_DUP_ENTRY') {
                return res.json({ success: false, message: '邮箱已注册' });
            }
            return res.json({ success: false, message: '注册失败', error: err.message });
        }
        console.log('注册成功，插入ID:', result && result.insertId);
        res.json({ success: true });
    });
});

// 登录接口
router.post('/api/login', (req, res) => {
    console.log('收到登录请求:', req.body); // 日志输出
    const { email, password } = req.body;
    db.query('SELECT * FROM user WHERE email=? AND password=?', [email, password], (err, results) => {
        if (err) {
            console.error('登录数据库错误:', err); // 日志输出
            return res.json({ success: false, message: '登录失败' });
        }
        if (results.length > 0) {
            res.json({ success: true });
        } else {
            res.json({ success: false, message: '邮箱或密码错误' });
        }
    });
});

module.exports = router;
