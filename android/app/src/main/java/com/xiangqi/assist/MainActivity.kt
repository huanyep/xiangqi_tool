package com.xiangqi.assist

import android.app.Activity
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.provider.Settings
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.button.MaterialButton
import com.google.android.material.textfield.TextInputEditText
import kotlinx.coroutines.*

/**
 * 象棋辅助 — 手机端主界面
 */
class MainActivity : AppCompatActivity() {

    private lateinit var ipInput: TextInputEditText
    private lateinit var portInput: TextInputEditText
    private lateinit var btnToggle: MaterialButton
    private lateinit var statusText: android.widget.TextView
    private lateinit var resultText: android.widget.TextView
    private lateinit var detailText: android.widget.TextView

    private var isRunning = false
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    private val overlayPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { /* 返回后检查权限 */ }

    private val mediaProjectionLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            startCaptureService(result.resultCode, result.data!!)
        } else {
            Toast.makeText(this, "需要截屏权限", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        ipInput = findViewById(R.id.ipInput)
        portInput = findViewById(R.id.portInput)
        btnToggle = findViewById(R.id.btnToggle)
        statusText = findViewById(R.id.statusText)
        resultText = findViewById(R.id.resultText)
        detailText = findViewById(R.id.detailText)

        // 加载上次保存的 IP
        val sp = getSharedPreferences("config", MODE_PRIVATE)
        ipInput.setText(sp.getString("server_ip", ""))
        portInput.setText(sp.getString("server_port", "5800"))

        btnToggle.setOnClickListener {
            if (isRunning) {
                stopCapture()
            } else {
                requestPermissionsAndStart()
            }
        }

        // 注册结果回调
        ScreenCaptureService.onResult = { result ->
            runOnUiThread {
                if (result != null) {
                    resultText.text = result.bestMove
                    detailText.text = "评分: ${result.score}  深度: ${result.depth}"
                    statusText.text = "分析中..."
                    // 更新悬浮窗
                    updateOverlay(result)
                } else {
                    statusText.text = "等待棋盘..."
                }
            }
        }
    }

    private fun updateOverlay(result: ApiClient.AnalysisResult) {
        if (OverlayService.isRunning) {
            val intent = Intent(this, OverlayService::class.java).apply {
                action = OverlayService.ACTION_UPDATE
                putExtra(OverlayService.EXTRA_RESULT, result)
            }
            startService(intent)
        } else {
            startService(Intent(this, OverlayService::class.java))
            // 等一秒后发送结果
            Handler(mainLooper).postDelayed({
                val intent = Intent(this, OverlayService::class.java).apply {
                    action = OverlayService.ACTION_UPDATE
                    putExtra(OverlayService.EXTRA_RESULT, result)
                }
                startService(intent)
            }, 1000)
        }
    }

    private fun getServerUrl(): String {
        val ip = ipInput.text?.toString()?.trim() ?: ""
        val port = portInput.text?.toString()?.trim() ?: "5800"
        return "http://$ip:$port"
    }

    private fun requestPermissionsAndStart() {
        // 1. 悬浮窗权限 (Android 6+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (!Settings.canDrawOverlays(this)) {
                AlertDialog.Builder(this)
                    .setTitle("需要悬浮窗权限")
                    .setMessage("为了显示走法建议，需要允许悬浮窗")
                    .setPositiveButton("去设置") { _, _ ->
                        val intent = Intent(
                            Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                            Uri.parse("package:$packageName")
                        )
                        overlayPermissionLauncher.launch(intent)
                    }
                    .show()
                return
            }
        }

        // 2. 通知权限 (Android 13+)
        if (Build.VERSION.SDK_INT >= 33) {
            if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
                != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 100)
            }
        }

        // 3. 请求截屏权限
        requestScreenCapture()
    }

    private fun requestScreenCapture() {
        val serverUrl = getServerUrl()
        if (serverUrl == "http://:5800") {
            Toast.makeText(this, "请输入电脑 IP 地址", Toast.LENGTH_SHORT).show()
            return
        }

        // 保存 IP
        val sp = getSharedPreferences("config", MODE_PRIVATE)
        sp.edit()
            .putString("server_ip", ipInput.text?.toString()?.trim())
            .putString("server_port", portInput.text?.toString()?.trim())
            .apply()

        val mpm = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        mediaProjectionLauncher.launch(mpm.createScreenCaptureIntent())
    }

    private fun startCaptureService(resultCode: Int, data: Intent) {
        val serverUrl = getServerUrl()
        val intent = Intent(this, ScreenCaptureService::class.java).apply {
            putExtra(ScreenCaptureService.EXTRA_RESULT_CODE, resultCode)
            putExtra(ScreenCaptureService.EXTRA_RESULT_DATA, data)
            putExtra(ScreenCaptureService.EXTRA_SERVER_URL, serverUrl)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }

        isRunning = true
        btnToggle.text = getString(R.string.btn_stop)
        statusText.text = "连接中..."
    }

    private fun stopCapture() {
        val intent = Intent(this, ScreenCaptureService::class.java).apply {
            action = ScreenCaptureService.ACTION_STOP
        }
        startService(intent)

        isRunning = false
        btnToggle.text = getString(R.string.btn_start)
        statusText.text = "已停止"
    }

    override fun onDestroy() {
        super.onDestroy()
        stopCapture()
        ScreenCaptureService.onResult = null
        scope.cancel()
    }
}
