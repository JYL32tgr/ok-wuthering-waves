import time

from src.char.BaseChar import BaseChar, SwitchPriority


class Lucilla(BaseChar):
    """Lucilla 自动战斗: 回路充能型 + 大招变身型角色。

    机制: 长按 E 或蓄力重击各攒 1 格回路能量, 攒满 3 格大招可用; 放大招后变身进入特殊形态
    (技能栏/大招图标消失, 视觉信号全失效), 固定时长输出后变回原建模, 再切人。
    """
    HOLD_TIME: float = 1.4
    LIBERATION_ANIMATION_TIME: float = 3.0
    LIBERATION_HEAVY_TIME: float = 15.0
    HEAVY_PULSE_TIME: float = 0.6
    CHARGE_TIME_OUT: float = 7.2
    LIBERATION_CD_SKIP: float = 1.5
    SWITCH_IN_SETTLE: float = 0.5

    def do_perform(self):
        if not self.perform_combat():
            self.switch_next_char()

    def perform_combat(self):
        """攒能量 -> 大招可用则放大招接输出.

        Returns:
            bool: 放出了大招(并已在 try_liberation 内切人)返回 True, 否则 False.
        """
        start = time.time()

        self.task.wait_until(lambda: self.task.in_team()[0], time_out=0.8)
        self.sleep(self.SWITCH_IN_SETTLE, check_combat=False)  # 等技能栏渲染稳定再判大招
        self.task.next_frame()

        if self.try_liberation():
            return True

        while time.time() - start < self.CHARGE_TIME_OUT:
            # 能量满但放不出(短CD / 切回UI未渲染读假 / 任何原因) -> 别溢出空攒, 直接切人
            if self.energy_full() and not self.liberation_available():
                self.logger.info('Lucilla energy full but liberation not castable, switch')
                break

            # 能量没满且大招在较长 CD -> 没必要攒, 切人省时间
            if not self.liberation_available() and self.task.get_cd('liberation') > self.LIBERATION_CD_SKIP:
                self.logger.info('Lucilla liberation on long cd, switch to save time')
                break    

            if self.try_liberation():
                return True

            self.charge_once()

        return False

    def charge_once(self):
        """攒 1 格回路能量: E 可用优先长按 E、否则蓄力重击.
        """
        if self.resonance_available():
            self.hold_resonance(self.HOLD_TIME)
        else:
            self.heavy_attack(self.HOLD_TIME)
        self.task.next_frame()

    def try_liberation(self):
        """大招就绪则放招(顺带先放声骸), 返回是否放出。
        """
        if not self.liberation_available():
            return False

        if self.echo_available():
            self.click_echo(time_out=0)
            
        self.perform_liberation()
        self.switch_next_char()
        return True

    def energy_full(self):
        """回路能量是否已满(解放图标高亮, 忽略CD)。
        """
        return self.available('liberation', check_color=True, check_cd=False)

    def perform_liberation(self):
        """放大招进入变身形态, 按住左键固定时长输出后切人.
        """
        if not self.task.use_liberation:
            return

        start = time.time()
        while self.liberation_available() and time.time() - start < 1.5:
            self.send_liberation_key()
            self.sleep(0.1, check_combat=False)
        self.record_liberation_use()
        self.logger.info('Lucilla perform lib')

        # 前 3 秒大招动画特写阶段：保持 check_combat=False 防止镜头旋转引发误判
        self.sleep(self.LIBERATION_ANIMATION_TIME, check_combat=False)
        
        # 特写结束后进入变身重击阶段，恢复 check_combat=True，目标丢失或怪死时能立刻中断打断
        self.pulse_heavy_attack(self.LIBERATION_HEAVY_TIME)
        self.logger.info('Lucilla perform lib end')

    def pulse_heavy_attack(self, total_time):
        """变身后脉冲式重击 total_time 秒: 反复 mouse_down/sleep/mouse_up.
        """
        end = time.time() + total_time
        seen_active = False
        pulse_start = time.time()
        while time.time() < end:
            self.task.mouse_down()
            try:
                self.sleep(min(self.HEAVY_PULSE_TIME, end - time.time()), check_combat=True)
            finally:
                self.task.mouse_up()
            
            con = self.task.get_current_con()
            if con > 0.1:
                seen_active = True
            elif seen_active and con < 0.05:
                self.logger.info('Lucilla transform ended, stop pulse heavy early')
                break
            elif not seen_active and (time.time() - pulse_start > 2.0):
                self.logger.info('Lucilla transform not active or target lost, stop pulse heavy early')
                break
                
            self.sleep(0.02, check_combat=True) 

    def hold_resonance(self, duration):
        """长按共鸣技能键一段时间 (攒 1 格回路能量)。
        """
        self.task.send_key_down(self.get_resonance_key())
        try:
            self.sleep(duration, check_combat=True)
        finally:
            self.task.send_key_up(self.get_resonance_key())
        self.record_resonance_use()

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if has_intro and current_char and current_char.char_name in {'char_verina', 'char_shorekeeper'}:
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)
