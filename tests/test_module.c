#define DX213_HOST_TEST
#include "../dx213_boot.c"
static int cases;
static void reset(void)
{
    unsigned int i;
    memset(&test_pci,0,sizeof(test_pci));
    memset(&test_host,0,sizeof(test_host));
    memset(test_ports,0,sizeof(test_ports));
    memset(&test_uts,0,sizeof(test_uts));
    strcpy(test_uts.release,"4.4.302+");
    strcpy(test_uts.version,"#90080 SMP Wed Jul 22 00:08:29 CST 2026");
    strcpy(test_uts.machine,"x86_64");
    test_model_ok=test_symbol_ok=test_bytes_ok=test_pci_present=true;
    test_reads=test_writes=test_refs=test_scr_error=0;
    test_sstatus=0;
    test_driver.name="ahci";
    test_pci.vendor=0x1b4b; test_pci.device=0x9235;
    test_pci.dev.driver=&test_driver; test_pci.data=&test_host;
    test_host.dev=&test_pci.dev; test_host.n_ports=4;
    for(i=0;i<4;i++) {
        test_host.ports[i]=&test_ports[i];
        test_ports[i].host=&test_host; test_ports[i].port_no=i;
        test_ports[i].print_id=3+i; test_ports[i].link.ap=&test_ports[i];
        test_ports[i].lock=&test_host.lock;
        test_ports[i].flags=ATA_FLAG_SATA|ATA_FLAG_PMP;
        test_ports[i].link.uiStsFlags=0x88;
    }
    action=1; isolated_test=true;
    raw_ports=pmp_links_snapshot=pmp_vendor=pmp_device=pmp_emid=refusal_detail=0;
    state=6; disk_mask=0; flags_snapshot=sstatus_snapshot=pmp_unique=device_class=0;
    test_schedules=0;
    memset(&test_shost,0,sizeof(test_shost));
    memset(test_links,0,sizeof(test_links));
    memset(&test_disk,0,sizeof(test_disk));
    memset(&test_virtual,0,sizeof(test_virtual));
    test_ops.error_handler=fake_op; test_ops.sched_eh=fake_op;
    test_ports[3].ops=&test_ops; test_ports[3].scsi_host=&test_shost;
    test_ports[3].PMSynoUnique=0x58;
    test_ports[3].link.device[0].class=ATA_DEV_PMP_UNSUP;
    test_ports[3].link.device[0].gscr[0]=0x1095;
    test_ports[3].link.device[0].gscr[1]=0x3726;
    test_ports[3].link.device[0].gscr[2]=5;
    test_sstatus=0x113;
}
static void check(int expected_rc,int expected_writes,unsigned int expected_flags)
{
    int old_dev_lock=test_pci.dev.lock.held,old_eh_lock=test_host.eh_mutex.held;
    int old_scan=test_ports[3].scsi_scan_mutex.held;
    int rc=dx213_init();
    assert(rc==expected_rc);
    assert(test_writes==expected_writes);
    assert(test_ports[3].link.uiStsFlags==expected_flags);
    assert(test_ports[0].link.uiStsFlags==0x88);
    assert(test_ports[1].link.uiStsFlags==0x88);
    assert(test_ports[2].link.uiStsFlags==0x88);
    assert(!test_refs && !test_host.lock);
    assert(test_pci.dev.lock.held==old_dev_lock);
    assert(test_host.eh_mutex.held==old_eh_lock);
    assert(test_ports[3].scsi_scan_mutex.held==old_scan);
    assert(test_schedules==expected_writes);
    ++cases;
}

#define REFUSE(setup,err) do {reset(); setup; check(err,0,0x88);} while(0)
int main(void) {
 unsigned int i,bit;
 reset();action=0;isolated_test=false;check(0,0,0x88);assert(state==2);
 reset();check(0,1,0x80);assert(state==3);dx213_exit();assert(test_ports[3].link.uiStsFlags==0x80);
 reset();test_sstatus=0;check(0,0,0x88);assert(state==1);
 REFUSE(isolated_test=false,-EINVAL);
 REFUSE(action=2,-EINVAL);
 REFUSE(test_uts.version[0]='x',-EINVAL);
 REFUSE(test_model_ok=false,-EINVAL);
 REFUSE(test_symbol_ok=false,-EINVAL);
 REFUSE(test_bytes_ok=false,-EINVAL);
 REFUSE(test_pci_present=false,-ENODEV);
 REFUSE(test_pci.device=0,-ENODEV);
 REFUSE(test_pci.dev.lock.held=1,-EBUSY);
 REFUSE(test_pci.dev.driver=NULL,-ENODEV);
 REFUSE(test_pci.current_state=3,-EBUSY);
 REFUSE(test_host.n_ports=3,-EINVAL);
 REFUSE(test_ports[3].port_no=1,-EINVAL);
 REFUSE(test_ports[3].print_id=4,-EINVAL);
 REFUSE(test_ports[3].ops=NULL,-EINVAL);
 REFUSE(test_ports[3].scsi_host=NULL,-EINVAL);
 REFUSE(test_ops.sched_eh=NULL,-EINVAL);
 REFUSE(test_ports[3].scsi_scan_mutex.held=1,-EBUSY);
 REFUSE(test_host.eh_mutex.held=1,-EBUSY);
 for(i=0;i<4;i++)for(bit=1;bit;bit<<=1)if(bit&BUSY_FLAGS){
  reset();test_ports[i].pflags=bit;check(-EBUSY,0,0x88);
 }
 REFUSE(test_host.eh_owner=&test_host,-EBUSY);
 REFUSE(test_shost.recovery=1,-EBUSY);
 REFUSE(test_ports[3].hotplug_task.work.busy=1,-EBUSY);
 REFUSE(test_ports[3].scsi_rescan_task.busy=1,-EBUSY);
 reset();test_ports[3].link.uiStsFlags |= SYNO_STATUS_GPIO_CTRL;
 check(-EBUSY,0,0x88 | SYNO_STATUS_GPIO_CTRL);
 REFUSE(test_ports[3].qc_active=1,-EBUSY);
 REFUSE(test_ports[3].nr_active_links=1,-EBUSY);
 REFUSE(test_scr_error=-EIO,-EIO);
 REFUSE(test_ports[3].pmp_link=test_links,-EINVAL);
 for(i=0;i<2;i++) {reset();test_ports[3].link.device[i].enabled=true;check(-EINVAL,0,0x88);}
 REFUSE(test_ports[3].link.device[0].sdev=&test_disk,-EINVAL);
 REFUSE(test_ports[3].PMSynoUnique=0x54,-EINVAL);
 REFUSE(test_ports[3].PMSynoEMID=1,-EINVAL);
 REFUSE(test_ports[3].link.device[0].gscr[0]=0,-EINVAL);
 REFUSE(test_ports[3].link.device[0].gscr[1]=0,-EINVAL);
 REFUSE(test_ports[3].link.device[0].gscr[2]=0,-EINVAL);
 for(i=1;i<16;i++)if(i!=3){reset();test_sstatus=i;check(-EINVAL,0,0x88);}
 REFUSE(test_ports[3].link.eh_info.action=1,-EBUSY);
 REFUSE(test_ports[3].link.eh_info.probe_mask=1,-EBUSY);
 reset(); test_virtual.type=3;test_virtual.channel=15;
 test_ports[3].link.device[0].sdev=&test_virtual;check(0,1,0x80);
 reset(); action=0; test_ports[3].qc_active=1;check(0,0,0x88);assert(state==5);
 reset(); action=0;test_ports[3].PMSynoUnique=0;check(0,0,0x88);assert(state==6);
 /* Already attached data disk: inspect reports readiness; apply never reprobes. */
 for(i=0;i<2;i++) {
  reset();action=i;test_ports[3].link.uiStsFlags=0x80;
  test_ports[3].nr_pmp_links=5;test_ports[3].pmp_link=test_links;
  test_links[0].device[0].enabled=true;test_links[0].device[0].class=ATA_DEV_ATA;
  test_links[0].device[0].sdev=&test_disk;test_disk.sdev_state=SDEV_RUNNING;
  check(i ? -EALREADY : 0,0,0x80);assert(state==4 && disk_mask==1);
 }
 /* Regression: distinguish raw GSCR port count from attached link count. */
 reset();action=0;test_ports[3].link.uiStsFlags=0;
 test_ports[3].nr_pmp_links=5;test_ports[3].pmp_link=test_links;
 test_ports[3].link.device[0].gscr[2]=6;
 test_ports[3].link.device[0].class=5;
 test_links[0].device[0].enabled=true;test_links[0].device[0].class=ATA_DEV_ATA;
 test_links[0].device[0].sdev=&test_disk;test_disk.sdev_state=SDEV_RUNNING;
 check(0,0,0);assert(state==4 && disk_mask==1 && refusal_detail==0);
 assert(raw_ports==6 && pmp_links_snapshot==5 && pmp_vendor==0x1095);
 /* Six raw ports also accepted before attachment; preserve other guards. */
 reset();test_ports[3].link.device[0].gscr[2]=6;
 check(0,1,0x80);assert(state==3);
 reset();action=0;test_ports[3].link.device[0].gscr[2]=6;
 check(0,0,0x88);assert(state==2);
 REFUSE(test_ports[3].link.device[0].gscr[2]=7,-EINVAL);
 reset();action=0;test_ports[3].link.uiStsFlags=0;
 test_ports[3].link.device[0].gscr[2]=6;
 test_ports[3].nr_pmp_links=6;test_ports[3].pmp_link=test_links;
 check(0,0,0);assert(state==6 && refusal_detail==2);
 printf("PASS: %d module control-flow cases; no hardware simulation claim\n",cases);
 return 0;
}
