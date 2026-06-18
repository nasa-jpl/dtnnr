import { ScrollArea, Tabs, useMatches } from '@mantine/core';
import { Outlet, useLocation, useNavigate } from '@tanstack/react-router';
import { Route as allocatorsRoute } from '../routes/_home.allocators';
import { Route as hostsRoute } from '../routes/_home.hosts';
import { Route as nodesRoute } from '../routes/_home.nodes';
import { Route as operatorsRoute } from '../routes/_home.operators';
import classes from './Home.module.css';

function Home() {
  const orientation = useMatches({
    base: 'horizontal',
    sm: 'vertical',
  });
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className={classes.homeWrapper}>
      <ScrollArea
        className={classes.tabsContainer}
        type="scroll"
        scrollbarSize={4}
        scrollHideDelay={500}
      >
        <Tabs
          defaultValue={location.pathname}
          orientation={orientation}
          value={location.pathname}
          onChange={(value) => navigate({ to: value })}
        >
          <Tabs.List className={classes.tabsList}>
            {/* <Tabs.Tab value="/home">General</Tabs.Tab> */}
            <Tabs.Tab value={nodesRoute.to}>Nodes</Tabs.Tab>
            <Tabs.Tab value={allocatorsRoute.to}>Allocators</Tabs.Tab>
            <Tabs.Tab value={operatorsRoute.to}>Operators</Tabs.Tab>
            <Tabs.Tab value={hostsRoute.to}>Hosts</Tabs.Tab>
          </Tabs.List>
        </Tabs>
      </ScrollArea>
      <div className={classes.homePanel}>
        <Outlet />
      </div>
    </div>
  );
}

export default Home;
